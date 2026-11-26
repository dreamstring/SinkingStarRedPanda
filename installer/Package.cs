using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Security.Cryptography;

public record PluginFile(string source, string target, string sha256, string? migrateFrom = null, string? stockFrom = null);
public record Entry(string target, string installed, string? original);

public static class Package
{
    const string State = ".panda-install";
    public static bool HasReceipt(string game) =>
        File.Exists(Path.Combine(game, State, "receipt.json"));
    static string Hash(string file)
    {
        using var stream = File.OpenRead(file);
        return Convert.ToHexString(SHA256.HashData(stream));
    }

    static string Resolve(string root, string relative)
    {
        var path = Path.GetFullPath(root);
        foreach (var part in relative.Split('/', '\\'))
        {
            if (part.Length == 0 || part.EndsWith('.') || part.EndsWith(' ') ||
                part.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0 ||
                Regex.IsMatch(part, @"^(CON|NUL|PRN|AUX|COM[1-9]|LPT[1-9])(\.|$)", RegexOptions.IgnoreCase))
                throw new InvalidDataException(relative);
            path = Path.Combine(path, part);
            try {
                if (File.GetAttributes(path).HasFlag(FileAttributes.ReparsePoint))
                    throw new InvalidDataException(path);
            } catch (FileNotFoundException) {} catch (DirectoryNotFoundException) {}
        }
        return path;
    }

    static string Target(string game, string relative)
    {
        if (relative.Split('/', '\\')[0].Equals(State,StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException(relative);
        return Resolve(game,relative);
    }

    static IDisposable Lock(string game)
    {
        if (!File.Exists(Resolve(game,"sinking_star.exe"))) throw new FileNotFoundException("sinking_star.exe");
        return new FileStream(Resolve(game,".panda-lock"),FileMode.CreateNew,FileAccess.Write,
            FileShare.None,4096,FileOptions.DeleteOnClose);
    }

    public static void Install(string game, string manifest)
    {
        using var guard = Lock(game);
        if (!HasReceipt(game)) { InstallFresh(game,manifest); return; }
        var state = Resolve(game,State);
        var entries = JsonSerializer.Deserialize<Entry[]>(File.ReadAllText(Resolve(state,"receipt.json")))
            ?? throw new InvalidDataException(state);
        var rollback = Directory.CreateTempSubdirectory("panda-upgrade-").FullName;
        bool retainRollback = false;
        try {
            var previous = new List<PluginFile>();
            foreach (var entry in entries) {
                var source = previous.Count+".previous";
                var copy = Path.Combine(rollback,source);
                File.Copy(Target(game,entry.target),copy);
                if (Hash(copy) != entry.installed) throw new IOException(entry.target);
                previous.Add(new(source,entry.target,entry.installed));
            }
            var previousManifest = Path.Combine(rollback,"plugin.json");
            File.WriteAllText(previousManifest,JsonSerializer.Serialize(previous));
            Restore(game);
            try { InstallFresh(game,manifest); }
            catch {
                try { InstallFresh(game,previousManifest,allowEmptyReceipt:true); }
                catch (Exception recovery) {
                    retainRollback = true;
                    throw new IOException($"Recovery files: {rollback}",recovery);
                }
                throw;
            }
        } finally {
            if (!retainRollback) Directory.Delete(rollback,true);
        }
    }

    static void InstallFresh(string game, string manifest, bool allowEmptyReceipt = false)
    {
        var files = JsonSerializer.Deserialize<PluginFile[]>(File.ReadAllText(manifest));
        if (files == null || (files.Length == 0 && !allowEmptyReceipt)) throw new InvalidDataException(manifest);
        var state = Resolve(game,State);
        if (Directory.Exists(state)) throw new IOException(state);
        var entries = new List<Entry>();
        var targets = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var newDirectories = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        Directory.CreateDirectory(state);
        try {
            foreach (var file in files) {
                var target = Target(game,file.target);
                if (!targets.Add(target) || Directory.Exists(target)) throw new InvalidDataException(target);
                if (file.migrateFrom != null) {
                    var current = Hash(target);
                    if (current.Equals(file.sha256, StringComparison.OrdinalIgnoreCase)) continue;
                    if (!current.Equals(file.migrateFrom, StringComparison.OrdinalIgnoreCase) &&
                        !current.Equals(file.stockFrom, StringComparison.OrdinalIgnoreCase))
                        throw new InvalidDataException($"Unrecognized game asset: {file.target}");
                }
                for (var dir = Path.GetDirectoryName(target); dir != null && !Directory.Exists(dir);
                     dir = Path.GetDirectoryName(dir))
                    newDirectories.Add(Path.GetRelativePath(game, dir));
                var stage = Path.Combine(state,entries.Count+".new");
                File.Copy(Resolve(Path.GetDirectoryName(Path.GetFullPath(manifest))!,file.source),stage);
                var installed = Hash(stage);
                if (!string.Equals(installed, file.sha256, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException($"SHA-256 mismatch: {file.source}");
                string? original = null;
                if (File.Exists(target)) {
                    var backup = Path.Combine(state,entries.Count+".bak");
                    File.Copy(target,backup);
                    original = Hash(backup);
                }
                entries.Add(new(file.target,installed,original));
            }
            File.WriteAllText(Path.Combine(state,"directories.json"), JsonSerializer.Serialize(newDirectories));
            File.WriteAllText(Path.Combine(state,"pending"),JsonSerializer.Serialize(entries));
            File.Move(Path.Combine(state,"pending"),Path.Combine(state,"receipt.json"));
            for (int i=0;i<entries.Count;i++) {
                var target = Target(game,entries[i].target);
                Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                File.Move(Path.Combine(state,i+".new"),target,true);
            }
        } catch {
            if (File.Exists(Path.Combine(state,"receipt.json"))) Restore(game);
            else Directory.Delete(state,true);
            throw;
        }
    }

    public static void Uninstall(string game)
    {
        using var guard = Lock(game);
        Restore(game);
    }

    static void Restore(string game)
    {
        var state = Resolve(game,State);
        var entries = JsonSerializer.Deserialize<Entry[]>(File.ReadAllText(Resolve(state,"receipt.json"))!)
            ?? throw new InvalidDataException(state);
        for (int i=0;i<entries.Length;i++) {
            var e = entries[i];
            var target = Target(game,e.target);
            var current = File.Exists(target) ? Hash(target) : null;
            if (current != e.original && current != e.installed) throw new IOException(target);
            if (e.original != null && Hash(Resolve(state,i+".bak")) != e.original)
                throw new InvalidDataException(target);
        }
        for (int i=entries.Length-1;i>=0;i--) {
            var e = entries[i];
            var target = Target(game,e.target);
            if (e.original == null) { if (File.Exists(target)) File.Delete(target); }
            else if (Hash(target) != e.original) {
                var temp = Resolve(state,i+".restore");
                File.Copy(Resolve(state,i+".bak"),temp,true);
                File.Move(temp,target,true);
            }
        }
        var directoryReceipt = Resolve(state,"directories.json");
        if (File.Exists(directoryReceipt)) {
            var directories = JsonSerializer.Deserialize<string[]>(File.ReadAllText(directoryReceipt))
                ?? throw new InvalidDataException(directoryReceipt);
            foreach (var relative in directories.OrderByDescending(name => name.Length)) {
                var dir = Target(game, relative);
                if (Directory.Exists(dir) && !Directory.EnumerateFileSystemEntries(dir).Any())
                    Directory.Delete(dir);
            }
        }
        Directory.Delete(state,true);
    }
}

