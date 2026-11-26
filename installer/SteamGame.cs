using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;
using Microsoft.Win32;

internal static class SteamGame
{
    internal static string Find()
    {
        var roots = new[] {
            Registry.GetValue(@"HKEY_CURRENT_USER\Software\Valve\Steam", "SteamPath", null) as string,
            Registry.GetValue(@"HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath", null) as string,
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Steam")
        };
        foreach (var steam in roots) {
            if (string.IsNullOrWhiteSpace(steam)) continue;
            var libraries = new List<string> { steam };
            var config = Path.Combine(steam, "steamapps", "libraryfolders.vdf");
            if (File.Exists(config))
                foreach (Match entry in Regex.Matches(File.ReadAllText(config), @"""path""\s*""([^""]+)""", RegexOptions.IgnoreCase))
                    libraries.Add(entry.Groups[1].Value.Replace(@"\\", @"\"));
            foreach (var library in libraries) {
                var apps = Path.Combine(library, "steamapps");
                var manifest = Path.Combine(apps, "appmanifest_499170.acf");
                if (!File.Exists(manifest)) continue;
                var name = Regex.Match(File.ReadAllText(manifest), @"""installdir""\s*""([^""]+)""", RegexOptions.IgnoreCase).Groups[1].Value;
                if (name.Length == 0 || name != Path.GetFileName(name)) continue;
                var game = Path.GetFullPath(Path.Combine(apps, "common", name));
                if (File.Exists(Path.Combine(game, "sinking_star.exe"))) return game;
            }
        }
        return "";
    }
}
