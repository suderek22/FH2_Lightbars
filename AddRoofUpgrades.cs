using System;
using System.IO;
using System.Linq;
using System.Numerics;
using System.Runtime.Loader;
using ForzaTools.CarScene;

static class AddRoofUpgrades
{
    static CarbinFile Read(string path)
    {
        var car = new CarbinFile();
        using (var input = File.OpenRead(path)) car.Load(input);
        return car;
    }

    static void Main(string[] args)
    {
        string libraries = Path.GetFullPath(args[0]);
        AssemblyLoadContext.Default.Resolving += (context, name) => {
            string path = Path.Combine(libraries, name.Name + ".dll");
            return File.Exists(path) ? context.LoadFromAssemblyPath(path) : null;
        };
        Prepare(args);
    }

    static void Prepare(string[] args)
    {
        string stockPath = args[1], referencePath = args[2], outputPath = args[3];
        int bodyId = int.Parse(args[4]);
        int firstId = args.Length > 8 ? int.Parse(args[8]) : bodyId + 1;
        string mediaName = args[5].ToLowerInvariant();
        var shift = new Vector4(0f, float.Parse(args[6], System.Globalization.CultureInfo.InvariantCulture),
                                  float.Parse(args[7], System.Globalization.CultureInfo.InvariantCulture), 0f);
        var car = Read(stockPath);
        using (var roundTrip = new MemoryStream()) {
            car.Save(roundTrip);
            if (!roundTrip.ToArray().SequenceEqual(File.ReadAllBytes(stockPath)))
                throw new InvalidDataException("The stock scene cannot be saved without modifications.");
        }

        var reference = Read(referencePath).Scene.UpgradableParts.Single(part => part.Type == CCarParts.Hood);
        var hood = car.Scene.UpgradableParts.SingleOrDefault(part => part.Type == CCarParts.Hood);
        if (hood == null) {
            var stockModels = car.Scene.NonUpgradableParts
                .SelectMany(entry => entry.Part.Models.Select(model => (entry, model)))
                .Where(item => item.model.Path.IndexOf(@"\exterior\hood\", StringComparison.OrdinalIgnoreCase) >= 0)
                .ToArray();
            if (stockModels.Length == 0) throw new InvalidDataException("The stock scene has no hood models.");
            var sourceStock = reference.Upgrades.Single(upgrade => upgrade.IsStock);
            hood = new UpgradablePart {
                Version = reference.Version, Type = CCarParts.Hood,
                Upgrades = { new Upgrade {
                    Version = sourceStock.Version, Id = bodyId, Level = 0, IsStock = true,
                    CarBodyId = bodyId, ParentIsStock = sourceStock.ParentIsStock,
                    Bounds = stockModels[0].entry.Part.Bounds
                } }
            };
            foreach (var (entry, model) in stockModels) {
                entry.Part.Models.Remove(model);
                hood.SharedModels.Add(new SharedCarModel { UpgradeIds = { bodyId }, Model = model });
            }
            foreach (var entry in stockModels.Select(item => item.entry).Distinct())
                if (entry.Part.Models.Count == 0) car.Scene.NonUpgradableParts.Remove(entry);
            car.Scene.UpgradableParts.Add(hood);
        }

        var stock = hood.Upgrades.Single(upgrade => upgrade.IsStock && upgrade.Id == bodyId);
        var shared = hood.SharedModels.Where(model => model.UpgradeIds.Contains(bodyId)).ToArray();
        if (shared.Length == 0 && stock.Models.Count == 0)
            throw new InvalidDataException("Unexpected existing hood model or upgrade layout.");

        var referenceBar = reference.SharedModels.Where(model =>
            model.Model.Path.IndexOf(@"\lightbars\", StringComparison.OrdinalIgnoreCase) >= 0).ToArray();
        for (int index = 0; index < 2; ++index) {
            string color = index == 0 ? "amber" : "blue";
            var source = referenceBar.Single(model => model.Model.Path.EndsWith(
                "lightbar_" + color + "_modern_a.modelbin", StringComparison.OrdinalIgnoreCase));
            var referenceUpgrade = reference.Upgrades.Single(upgrade => upgrade.Id == source.UpgradeIds.Single());
            int id = firstId + index;
            if (hood.Upgrades.Any(upgrade => upgrade.Id == id)) throw new InvalidDataException("Upgrade ID already in use.");
            var model = source.Model;
            if (model.Transform != Matrix4x4.Identity || model.BoneName != "<root>")
                throw new InvalidDataException("Unexpected reference lightbar attachment.");
            model.Path = model.Path.Replace("alf_4c_14", mediaName);
            hood.Upgrades.Add(new Upgrade {
                Version = stock.Version, Id = id, Level = referenceUpgrade.Level,
                IsStock = false, CarBodyId = bodyId, ParentIsStock = stock.ParentIsStock,
                Bounds = new AABB {
                    Min = Vector4.Min(stock.Bounds.Min, referenceUpgrade.Bounds.Min + shift),
                    Max = Vector4.Max(stock.Bounds.Max, referenceUpgrade.Bounds.Max + shift)
                }
            });
            hood.Upgrades.Last().Models.AddRange(stock.Models);
            foreach (var entry in shared) entry.UpgradeIds.Add(id);
            hood.SharedModels.Add(new SharedCarModel { UpgradeIds = { id }, Model = model });
        }

        using (var output = File.Create(outputPath)) car.Save(output);
        var verified = Read(outputPath).Scene.UpgradableParts.Single(part => part.Type == CCarParts.Hood);
        if (!verified.Upgrades.Any(upgrade => upgrade.Id == firstId)
            || !verified.Upgrades.Any(upgrade => upgrade.Id == firstId + 1)
            || verified.SharedModels.Count(model => model.Model.Path.Contains(@"\lightbars\")) != 2)
            throw new InvalidDataException("The saved hood did not reopen with the expected upgrade mappings.");
    }
}
