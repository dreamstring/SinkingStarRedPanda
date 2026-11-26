using System;
using System.IO;
using System.Text.Json;
public static class Checks
{
    public static int Run()
    {
        var root=Directory.CreateDirectory(Path.Combine(AppContext.BaseDirectory,"test-"+Guid.NewGuid())).FullName;
        try {
            var game=Directory.CreateDirectory(Path.Combine(root,"game")).FullName;
            File.WriteAllText(Path.Combine(game,"sinking_star.exe"),"fixture");
            var log=Directory.CreateDirectory(Path.Combine(game,"logs")).FullName;
            File.WriteAllText(Path.Combine(log,"log_1.txt"),"[Steam] Game language is 'schinese' => CHINESE_SIMPLIFIED");
            void Check(bool ok){if(!ok)throw new Exception("Assertion failed");}
            Check(Language.Read(game)[0]=="游戏目录");
            var steamGame = Directory.CreateDirectory(Path.Combine(root,"steamapps","common","Order of the Sinking Star")).FullName;
            var config = Path.Combine(root,"steamapps","appmanifest_499170.acf");
            File.WriteAllText(config, "\"UserConfig\" { \"language\" \"tchinese\" }");
            Check(Language.Read(steamGame)[0]=="遊戲目錄");
            var old=Path.Combine(game,"old"); var added=Path.Combine(game,"added");
            File.WriteAllText(old,"original"); File.WriteAllText(Path.Combine(root,"payload"),"plugin");
            var manifest=Path.Combine(root,"plugin.json");
            var digest = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(Path.Combine(root,"payload"))));
            void Plan(string second)=>File.WriteAllText(manifest,JsonSerializer.Serialize(new[]{new PluginFile("payload","old",digest),new PluginFile("payload",second,digest)}));
            Plan("added"); Package.Install(game,manifest);
            Check(File.ReadAllText(old)=="plugin" && File.ReadAllText(added)=="plugin");
            Package.Install(game,manifest);
            File.WriteAllText(Path.Combine(root,"v2"),"updated");
            File.WriteAllText(manifest,JsonSerializer.Serialize(new[]{new PluginFile("v2","old",digest)}));
            try {Package.Install(game,manifest); throw new Exception("Expected invalid upgrade");}
            catch(InvalidDataException){}
            Check(File.ReadAllText(old)=="plugin" && File.ReadAllText(added)=="plugin");
            var updatedDigest=Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(Path.Combine(root,"v2"))));
            File.WriteAllText(manifest,JsonSerializer.Serialize(new[]{new PluginFile("v2","old",updatedDigest)}));
            Package.Install(game,manifest);
            Check(File.ReadAllText(old)=="updated" && !File.Exists(added));
            Package.Uninstall(game); Check(File.ReadAllText(old)=="original" && !File.Exists(added));
            Plan("old/child");
            try {Package.Install(game,manifest); throw new Exception("Expected failure");} catch(IOException){}
            Check(File.ReadAllText(old)=="original" && !Directory.Exists(Path.Combine(game,".panda-install")));
            Plan("added");
            File.WriteAllText(Path.Combine(root,"payload"),"damaged");
            try {Package.Install(game,manifest); throw new Exception("Expected checksum failure");}
            catch(InvalidDataException){}
            Check(File.ReadAllText(old)=="original" && !File.Exists(added) && !Directory.Exists(Path.Combine(game,".panda-install")));
            var stockDigest=Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(old)));
            File.WriteAllText(manifest,JsonSerializer.Serialize(new[]{new PluginFile("unused","old",stockDigest,digest)}));
            Package.Install(game,manifest);
            Plan("added");
            try {Package.Install(game,manifest); throw new Exception("Expected invalid upgrade of migration-only installation");}
            catch(InvalidDataException){}
            Check(Package.HasReceipt(game) && File.ReadAllText(old)=="original" && !File.Exists(added));
            Package.Uninstall(game);
            return 0;
        } catch(Exception e){File.WriteAllText(Path.Combine(root,"failure.txt"),e.ToString());return 1;}
        finally {if(!File.Exists(Path.Combine(root,"failure.txt"))) Directory.Delete(root,true);}
    }
}
