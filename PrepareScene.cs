using System;
using System.IO;
using System.Linq;
using System.Numerics;
using System.Runtime.Loader;
using System.Text.Json;
using ForzaTools.Bundles;
using ForzaTools.Bundles.Blobs;
using ForzaTools.CarScene;

static class PrepareScene
{
    static void Main(string[] args)
    {
        AssemblyLoadContext.Default.Resolving += (context, name) => {
            var path = Path.Combine(Path.GetFullPath(args[0]), name.Name + ".dll");
            return File.Exists(path) ? context.LoadFromAssemblyPath(path) : null;
        };
        Prepare(args[1]);
    }

    static CarbinFile ReadScene(string path)
    {
        var result = new CarbinFile();
        using (var input = File.OpenRead(path)) result.Load(input);
        return result;
    }

    static void Prepare(string directory)
    {
        var stockPath = Path.Combine(directory, "fh2-ALF_4C_14.carbin");
        var stock = ReadScene(stockPath);
        var source = ReadScene(Path.Combine(directory, "fh6-ALF_4C_14.carbin"));
        using (var original = new MemoryStream()) {
            stock.Save(original);
            if (!original.ToArray().SequenceEqual(File.ReadAllBytes(stockPath)))
                throw new InvalidDataException("The FH2 scene does not round-trip unchanged.");
        }
        var skirts = stock.Scene.UpgradableParts.Single(part => part.Type.ToString() == "SideSkirts");
        var sourceSkirts = source.Scene.UpgradableParts.Single(part => part.Type.ToString() == "SideSkirts");
        var baseUpgrade = skirts.Upgrades.Single(upgrade => upgrade.Id == 2038000 && upgrade.IsStock);
        var stockMeshes = skirts.SharedModels.Where(model => model.UpgradeIds.Contains(baseUpgrade.Id)).ToArray();
        if (stockMeshes.Length == 0 || baseUpgrade.Models.Count != 0)
            throw new InvalidDataException("Unexpected FH2 stock side-skirt layout.");
        foreach (var variant in new[] { "amber", "blue" }) {
            var sourceName = "Lightbar_" + variant + "_modern_a.modelbin";
            var sourceModel = sourceSkirts.SharedModels.Single(model => model.Model.Path.EndsWith(sourceName, StringComparison.OrdinalIgnoreCase));
            var id = sourceModel.UpgradeIds.Single();
            if (id != (variant == "amber" ? 2038001 : 2038002) || skirts.Upgrades.Any(upgrade => upgrade.Id == id)
                || sourceModel.Model.Transform != Matrix4x4.Identity || sourceModel.Model.BoneName != "<root>")
                throw new InvalidDataException("Unexpected lightbar upgrade ID or attachment.");
            var bounds = ExportMesh(directory, sourceName, variant);
            var upgrade = sourceSkirts.Upgrades.Single(item => item.Id == id);
            skirts.Upgrades.Add(new Upgrade {
                Version = baseUpgrade.Version, Level = upgrade.Level, Id = upgrade.Id,
                IsStock = false, ParentIsStock = baseUpgrade.ParentIsStock, CarBodyId = baseUpgrade.CarBodyId,
                Bounds = new AABB {
                    Min = Vector4.Min(baseUpgrade.Bounds.Min, new Vector4(bounds.Item1, 0)),
                    Max = Vector4.Max(baseUpgrade.Bounds.Max, new Vector4(bounds.Item2, 0))
                }
            });
            foreach (var mesh in stockMeshes) mesh.UpgradeIds.Add(id);
            var model = new CarRenderModel {
                Version = stockMeshes[0].Model.Version,
                Path = string.Join((char)92, new[] { "game:", "media", "cars", "alf_4c_14", "scene", "exterior", "lightbars", sourceName.ToLowerInvariant() }),
                Transform = sourceModel.Model.Transform, LODDetails = sourceModel.Model.LODDetails,
                BoneName = sourceModel.Model.BoneName, BoneId = sourceModel.Model.BoneId,
                DrawGroups = stockMeshes[0].Model.DrawGroups,
                RawDrawGroupsValue = stockMeshes[0].Model.RawDrawGroupsValue,
                AssemblyName = "SideSkirts"
            };
            skirts.SharedModels.Add(new SharedCarModel { UpgradeIds = { id }, Model = model });
        }
        var outputPath = Path.Combine(directory, "ALF_4C_14.carbin");
        using (var output = File.Create(outputPath)) stock.Save(output);
        var verified = ReadScene(outputPath).Scene.UpgradableParts.Single(part => part.Type.ToString() == "SideSkirts");
        if (!verified.Upgrades.Select(item => item.Id).SequenceEqual(new[] { 2038000, 2038001, 2038002 }) ||
            verified.SharedModels.Count(model => model.Model.Path.Contains("lightbars")) != 2 ||
            verified.SharedModels.Where(model => model.Model.Path.Contains("sideskirts")).Any(model => model.UpgradeIds.Count != 3))
            throw new InvalidDataException("Reopened FH2 scene does not match the expected upgrade mapping.");
    }

    static Tuple<Vector3, Vector3> ExportMesh(string directory, string sourceName, string variant)
    {
        var bundle = new Bundle();
        using (var input = File.OpenRead(Path.Combine(directory, "fh6-" + sourceName))) bundle.Load(input);
        var meshes = bundle.Blobs.OfType<MeshBlob>().Select(mesh => new {
            mesh.LODFlags, mesh.MaterialId, mesh.RigidBoneIndex, mesh.VertexLayoutIndex,
            mesh.IndexBufferDrawOffset, mesh.IndexBufferOffset, mesh.IndexBufferIndex, mesh.IndexCount,
            mesh.IndexedVertexOffset, mesh.Is32BitIndices, mesh.Topology,
            Scale = new[] { mesh.PositionScale.X, mesh.PositionScale.Y, mesh.PositionScale.Z },
            Translate = new[] { mesh.PositionTranslate.X, mesh.PositionTranslate.Y, mesh.PositionTranslate.Z },
            Streams = mesh.VertexBuffers.Select(stream => new { stream.Index, stream.InputSlot, stream.Stride, stream.Offset })
        }).ToArray();
        if (meshes.Any(mesh => mesh.RigidBoneIndex != 1)) throw new InvalidDataException("Lightbar contains non-rigid geometry.");
        File.WriteAllText(Path.Combine(directory, variant + ".json"), JsonSerializer.Serialize(meshes));
        var scale = new Vector3(meshes[0].Scale[0], meshes[0].Scale[1], meshes[0].Scale[2]);
        var translation = new Vector3(meshes[0].Translate[0], meshes[0].Translate[1], meshes[0].Translate[2]);
        return Tuple.Create(translation - scale, translation + scale);
    }
}
