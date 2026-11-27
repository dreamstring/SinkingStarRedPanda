using System;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Text.RegularExpressions;
using Microsoft.Win32;

public static class Language
{
    static readonly string[] Codes = "english french german italian japanese koreana portuguese russian schinese spanish tchinese".Split();
    static readonly string[] Labels = {
        "Game folder|Browse|Install|Uninstall|Done|Play|Installed|Update plugin",
        "Dossier du jeu|Parcourir|Installer|Désinstaller|Terminé|Jouer|Installé|Mettre à jour",
        "Spielordner|Durchsuchen|Installieren|Deinstallieren|Fertig|Spielen|Installiert|Aktualisieren",
        "Cartella del gioco|Sfoglia|Installa|Disinstalla|Completato|Gioca|Installato|Aggiorna",
        "ゲームフォルダー|参照|インストール|アンインストール|完了|ゲーム起動|導入済み|更新",
        "게임 폴더|찾아보기|설치|제거|완료|게임 실행|설치됨|업데이트",
        "Pasta do jogo|Procurar|Instalar|Desinstalar|Concluído|Jogar|Instalado|Atualizar",
        "Папка игры|Обзор|Установить|Удалить|Готово|Играть|Установлено|Обновить",
        "游戏目录|浏览|安装插件|卸载插件|操作完成|打开游戏|已安装|更新插件",
        "Carpeta del juego|Examinar|Instalar|Desinstalar|Listo|Jugar|Instalado|Actualizar",
        "遊戲目錄|瀏覽|安裝外掛|解除安裝|操作完成|開啟遊戲|已安裝|更新外掛"
    };
    public static string[] Read(string game)
    {
        var logs = Path.Combine(game,"logs");
        if (Directory.Exists(logs))
            foreach (var file in new DirectoryInfo(logs).GetFiles("log_*.txt").OrderByDescending(f=>f.LastWriteTimeUtc)) {
                using var stream = new FileStream(file.FullName,FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete);
                using var reader = new StreamReader(stream);
                string? line;
                while ((line=reader.ReadLine()) != null) {
                    var match = Regex.Match(line,@"Game language is '([^']+)'");
                    var index = Array.IndexOf(Codes,match.Groups[1].Value == "brazilian" ? "portuguese" : match.Groups[1].Value);
                    if (index>=0) return Labels[index].Split('|');
                }
            }
        var common = Directory.GetParent(Path.GetFullPath(game));
        if (common?.Name.Equals("common", StringComparison.OrdinalIgnoreCase) == true && common.Parent != null)
        {
            var manifest = Path.Combine(common.Parent.FullName, "appmanifest_499170.acf");
            if (File.Exists(manifest))
            {
                var text = File.ReadAllText(manifest);
                var match = Regex.Match(text, @"""UserConfig""\s*\{[^{}]*?""language""\s*""([^""]+)""", RegexOptions.IgnoreCase);
                var language = match.Groups[1].Value.ToLowerInvariant();
                var index = Array.IndexOf(Codes, language == "brazilian" ? "portuguese" : language);
                if (index >= 0) return Labels[index].Split('|');
            }
        }
        return Labels[0].Split('|');
    }
}

public partial class InstallerWindow : Window
{
    void CloseWindow(object sender, RoutedEventArgs e) => Close();
    bool applying;
    string[] words = global::Language.Read(AppContext.BaseDirectory);
    public InstallerWindow()
    {
        InitializeComponent();
        Title += $" v{Package.BundledVersion}";
        Run(()=>{
            path.Text=SteamGame.Find();
            if(path.Text.Length>0) words=global::Language.Read(path.Text);
        });
        browse.Click+=(_,_)=>Run(()=>{
            var folder=new OpenFolderDialog();
            if(folder.ShowDialog(this)!=true) return;
            path.Text=folder.FolderName; status.Text=""; words=global::Language.Read(path.Text); Update();
        });
        launch.Click+=(_,_)=>Run(()=>System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(Path.Combine(path.Text,"sinking_star.exe")) { WorkingDirectory=path.Text, UseShellExecute=true }));
        install.Click+=async (_,_)=>await Apply(true);
        uninstall.Click+=async (_,_)=>await Apply(false);
        Closing+=(_,e)=>{ if (applying) e.Cancel=true; };
    }
    static string ManifestPath => Path.Combine(Path.GetDirectoryName(typeof(Package).Assembly.Location)!, "payload", "plugin.json");
    async Task Apply(bool installing)
    {
        if (applying) return;
        var game = path.Text;
        var manifest = ManifestPath;
        applying=true;
        status.Text=(installing ? install.Content : uninstall.Content)+"…";
        Update();
        try {
            await Task.Run(()=>{
                if (installing) Package.Install(game,manifest);
                else Package.Uninstall(game);
            });
            status.Text=words[4];
        } catch(Exception e){status.Text=e.Message;}
        finally { applying=false; Update(); }
    }
    void Update()
    {
        label.Text=words[0]; browse.Content=words[1]; install.Content=words[2]; uninstall.Content=words[3];
        var validGame = path.Text.Length > 0 && File.Exists(Path.Combine(path.Text, "sinking_star.exe"));
        var installed = validGame && Package.HasReceipt(path.Text);
        Version? version = null;
        if (installed) {
            try { version = Package.InstalledVersion(path.Text); }
            catch (Exception e) { status.Text = e.Message; }
        }
        bool upgrade = installed && version != null && version < Package.BundledVersion;
        label.Text = installed ? $"{words[0]}   ({words[6]} v{version?.ToString() ?? "?"})" : words[0];
        browse.IsEnabled = !applying;
        launch.Content = words[5];
        launch.IsEnabled = validGame && !applying;
        install.Content = upgrade ? words[7] : installed ? words[6] : words[2];
        install.SetResourceReference(Button.BackgroundProperty, installed && !upgrade ? "Control" : "Brand");
        uninstall.SetResourceReference(Button.BackgroundProperty, installed ? "Brand" : "Control");
        install.IsEnabled = validGame && (!installed || upgrade) && !applying;
        uninstall.IsEnabled = installed && !applying;
    }
    void Run(Action action)
    {
        try {action();} catch(Exception e){status.Text=e.Message;}
        finally { Update(); }
    }
    [STAThread] public static int Main(string[] args)
    {
        if(args.SequenceEqual(new[]{"--verify-payload"})) {
            var manifest = ManifestPath;
            var files = System.Text.Json.JsonSerializer.Deserialize<PluginFile[]>(File.ReadAllText(manifest))!;
            foreach (var file in files) {
                using var input = File.OpenRead(Path.Combine(Path.GetDirectoryName(manifest)!, file.source));
                if (!Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(input)).Equals(file.sha256, StringComparison.OrdinalIgnoreCase)) return 1;
            }
            return files.Length == 0 ? 1 : 0;
        }
        if(args.SequenceEqual(new[]{"--self-test"})) return Checks.Run();
        return new Application().Run(new InstallerWindow());
    }
}

