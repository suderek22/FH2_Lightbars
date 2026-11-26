using System;
using System.IO;
using System.Linq;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text.Json;
using System.Buffers.Binary;
using System.Numerics;
using ForzaTools.CarScene;

static class MergeScenes
{
    static void Main(string[] args)
    {
        AssemblyLoadContext.Default.Resolving += (_, name) =>
            AssemblyLoadContext.Default.LoadFromAssemblyPath(Path.GetFullPath(Path.Combine(args[0], name.Name + ".dll")));
        Merge(args[1], args[2], args[3]);
    }

    static void Require(bool valid, string reason)
    {
        if (!valid) throw new InvalidDataException(reason);
    }

    static CarbinFile Read(byte[] data)
    {
        var car = new CarbinFile();
        using var stream = new MemoryStream(data);
        car.Load(stream);
        return car;
    }

    static byte[] Save(CarbinFile car)
    {
        using var stream = new MemoryStream();
        car.Save(stream);
        return stream.ToArray();
    }

    static void Merge(string input, string patch, string output)
    {
        using var json = JsonDocument.Parse(File.ReadAllBytes(patch));
        var root = json.RootElement;
        string media = Path.GetFileNameWithoutExtension(input).ToLowerInvariant();
        Require(root.GetProperty("format").GetString() == "fh2-carbin-patch" &&
                root.GetProperty("format_version").GetInt32() == 1 &&
                root.GetProperty("media_name").GetString() == media, "Unsupported patch or media name.");

        byte[] original = File.ReadAllBytes(input);
        var scene = Read(original);
        Require(Save(scene).SequenceEqual(original), "Lightbars scene failed round-trip.");
        int[] hood = HoodIds(scene);
        int added = 0;
        foreach (var part in root.GetProperty("parts").EnumerateArray()) {
            Require(part.GetProperty("op").GetString() == "merge", "Unsupported part operation.");
            var key = (CCarParts)part.GetProperty("key").GetInt32();
            var models = scene.Scene.NonUpgradableParts.Single(p => p.Type == key).Part.Models;
            foreach (var change in part.GetProperty("models").EnumerateArray()) {
                var model = ParseModel(change, media);
                Require(!models.Any(m => m.GuidV13 == model.GuidV13), "Duplicate part model GUID.");
                models.Add(model);
                added++;
            }
        }
        foreach (var group in root.GetProperty("groups").EnumerateArray()) {
            Require(group.GetProperty("op").GetString() == "merge" &&
                    group.GetProperty("upgrades").GetArrayLength() == 0, "Unsupported group operation.");
            var key = (CCarParts)group.GetProperty("key").GetInt32();
            var target = scene.Scene.UpgradableParts.Single(p => p.Type == key);
            foreach (var change in group.GetProperty("models").EnumerateArray()) {
                var model = ParseModel(change, media);
                var ids = change.GetProperty("value").GetProperty("upgrade_ids").EnumerateArray().Select(x => x.GetInt32()).ToArray();
                Require(ids.Length > 0 && ids.All(id => target.Upgrades.Any(u => u.Id == id)), "Unknown plate upgrade association.");
                Require(!target.SharedModels.Any(m => m.Model.GuidV13 == model.GuidV13), "Duplicate group model GUID.");
                var shared = new SharedCarModel { Model = model };
                shared.UpgradeIds.AddRange(ids);
                target.SharedModels.Add(shared);
                added++;
            }
        }

        byte[] merged = Save(scene);
        var check = Read(merged);
        Require(Save(check).SequenceEqual(merged) && HoodIds(check).SequenceEqual(hood), "Merged scene failed validation.");
        // Removing exactly the inserted records must restore the unmodified Lightbars scene byte for byte.
        int removed = check.Scene.NonUpgradableParts.Sum(p => p.Part.Models.RemoveAll(m => IsPlate(m, media))) +
                      check.Scene.UpgradableParts.Sum(p => p.SharedModels.RemoveAll(m => IsPlate(m.Model, media)));
        Require(added > 0 && removed == added && Save(check).SequenceEqual(original), "Plate merge changed other scene records.");
        File.WriteAllBytes(output, merged);
        Console.WriteLine($"{media}: {added} plate model record(s)");
    }

    static int[] HoodIds(CarbinFile file) => file.Scene.UpgradableParts.Single(p => p.Type == CCarParts.Hood)
        .SharedModels.Where(m => m.Model.Path.Contains(@"\lightbars\")).SelectMany(m => m.UpgradeIds).OrderBy(id => id).ToArray();

    static bool IsPlate(CarRenderModel model, string media) =>
        model.Path.StartsWith($@"game:\media\cars\{media}\scene\exterior\hzn\", StringComparison.OrdinalIgnoreCase);

    static CarRenderModel ParseModel(JsonElement change, string media)
    {
        var row = change.GetProperty("value");
        string Text(string key) => row.GetProperty(key).GetString();
        int Number(string key) => row.GetProperty(key).GetInt32();
        byte[] Hex(string key) => Convert.FromHexString(Text(key));
        Require(change.GetProperty("op").GetString() == "upsert" &&
                change.GetProperty("key").GetString() == Text("guid") && Number("version") == 15 &&
                Number("flags") == 0 && Number("has_hash") == 0 &&
                row.GetProperty("material_overrides").GetArrayLength() == 0 &&
                Hex("hash_hex").Length == 0 && Hex("unknown14_hex").SequenceEqual(new byte[20]),
                "Unsupported plate model record.");

        byte[] transform = Hex("transform_hex");
        var matrix = Matrix4x4.Identity;
        Require(transform.Length == 64, "Invalid transform length.");
        float F(int i) => BinaryPrimitives.ReadSingleLittleEndian(transform.AsSpan(i * 4));
        matrix = new Matrix4x4(F(0),F(1),F(2),F(3),F(4),F(5),F(6),F(7),F(8),F(9),F(10),F(11),F(12),F(13),F(14),F(15));
        var flags = Hex("unknown11_hex");
        Require(flags.Length == 18 && Hex("unknown10_hex").Length == 1, "Invalid model flags.");
        uint Flag(int i) => BinaryPrimitives.ReadUInt32LittleEndian(flags.AsSpan(2 + i * 4));

        var model = new CarRenderModel {
            Version = 15, Path = Text("path"), Transform = matrix,
            LODDetails = new LODFlags(checked((ushort)Number("lod"))),
            BoneName = Text("bone_name"), BoneId = checked((short)Number("bone_index")),
            DrawGroups = new DrawGroups(Number("draw_groups")),
            BreakAmount = BinaryPrimitives.ReadSingleLittleEndian(Hex("unknown8_hex")),
            IsInteriorWindshield = Hex("unknown10_hex")[0] != 0,
            ReceivesImpact = flags[0] != 0, ReceivesSplatter = flags[1] != 0,
            ReceivesDamage = Flag(0), ReceivesDirt = Flag(1), ReceivesOil = Flag(2), ReceivesRubber = Flag(3),
            AssemblyName = Text("part_name"), GuidV13 = new Guid(Hex("guid")),
            HorizonUnkV15 = BinaryPrimitives.ReadInt32LittleEndian(Hex("unknown15_hex"))
        };
        Require(IsPlate(model, media), "Unexpected plate model path.");
        model.MaterialIndexes = row.GetProperty("material_indices").EnumerateArray().Select(x => new MaterialIndexEntry {
            Key = x.GetProperty("name").GetString(), Value = x.GetProperty("value").GetUInt64()
        }).ToList();
        model.AOMapInfos = row.GetProperty("ao_maps").EnumerateArray().Select(x => {
            byte[] fields = Convert.FromHexString(x.GetProperty("data_hex").GetString());
            Require(fields.Length == 27 && x.GetProperty("version").GetInt32() == 3, "Unsupported AO record.");
            return new AOMapInfo {
                Version = 3, Path = x.GetProperty("path").GetString(),
                PartType = (CCarParts)BinaryPrimitives.ReadInt32LittleEndian(fields),
                PartId = BinaryPrimitives.ReadInt32LittleEndian(fields.AsSpan(4)),
                DroppedModelInstanceGuid = new Guid(fields.AsSpan(8, 16)),
                IsDefault = fields[24] != 0, LodTest = unchecked((sbyte)fields[25]), LodValue = unchecked((sbyte)fields[26])
            };
        }).ToList();
        return model;
    }
}
