using System;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Text.RegularExpressions;
using Microsoft.Win32;

public static class Language
{
    static readonly string[] Codes = "english french german italian japanese koreana portuguese russian schinese spanish tchinese".Split();
    static readonly string[] Labels = {
        "Game folder|Browse|Install|Uninstall|Done",
        "Dossier du jeu|Parcourir|Installer|Désinstaller|Terminé",
        "Spielordner|Durchsuchen|Installieren|Deinstallieren|Fertig",
        "Cartella del gioco|Sfoglia|Installa|Disinstalla|Completato",
        "ゲームフォルダー|参照|インストール|アンインストール|完了",
        "게임 폴더|찾아보기|설치|제거|완료",
        "Pasta do jogo|Procurar|Instalar|Desinstalar|Concluído",
        "Папка игры|Обзор|Установить|Удалить|Готово",
        "游戏目录|浏览|安装插件|卸载插件|操作完成",
        "Carpeta del juego|Examinar|Instalar|Desinstalar|Listo",
        "遊戲目錄|瀏覽|安裝外掛|解除安裝|操作完成"
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

public class InstallerWindow : Window
{
    readonly TextBox path = new(){IsReadOnly=true,Padding=new Thickness(8)};
    readonly TextBlock label = new(), status = new(){TextWrapping=TextWrapping.Wrap};
    readonly Button browse = new(), install = new(), uninstall = new();
    string[] words = global::Language.Read(AppContext.BaseDirectory);
    public InstallerWindow()
    {
        Title="Sinking Star · Red Panda"; Width=530; Height=350; MinWidth=460; MinHeight=320;
        Background=new SolidColorBrush(Color.FromRgb(42,39,39)); Foreground=Brushes.White;
        WindowStartupLocation=WindowStartupLocation.CenterScreen;
        var panel=new StackPanel{Margin=new Thickness(26)};
        Content=panel;
        panel.Children.Add(new TextBlock{Text=Title,FontSize=25,Margin=new Thickness(0,0,0,20)});
        panel.Children.Add(label);
        var row=new DockPanel{Margin=new Thickness(0,6,0,15)};
        panel.Children.Add(row); DockPanel.SetDock(browse,Dock.Right); row.Children.Add(browse); row.Children.Add(path);
        var actions=new StackPanel{Orientation=Orientation.Horizontal};
        panel.Children.Add(actions); actions.Children.Add(install); actions.Children.Add(uninstall);
        foreach(var b in new[]{browse,install,uninstall}) b.Padding=new Thickness(12,6,12,6);
        install.Margin=new Thickness(0,0,8,0);
        status.Margin=new Thickness(0,12,0,0); panel.Children.Add(status);
        Update();
        browse.Click+=(_,_)=>Run(()=>{
            var folder=new OpenFolderDialog();
            if(folder.ShowDialog(this)!=true) return;
            path.Text=folder.FolderName; status.Text=""; words=global::Language.Read(path.Text); Update();
        });
        install.Click+=(_,_)=>Run(()=>{
            var manifest = Path.Combine(AppContext.BaseDirectory, "payload", "plugin.json");
            Package.Install(path.Text, manifest); status.Text=words[4];
        });
        uninstall.Click+=(_,_)=>Run(()=>{Package.Uninstall(path.Text); status.Text=words[4];});
    }
    void Update()
    {
        label.Text=words[0]; browse.Content=words[1]; install.Content=words[2]; uninstall.Content=words[3];
        install.IsEnabled=uninstall.IsEnabled=File.Exists(Path.Combine(path.Text,"sinking_star.exe")) && path.Text.Length>0;
    }
    void Run(Action action)
    {
        try {action();} catch(Exception e){status.Text=e.Message; Update();}
    }
    [STAThread] public static int Main(string[] args)
    {
        if(args.SequenceEqual(new[]{"--self-test"})) return Checks.Run();
        return new Application().Run(new InstallerWindow());
    }
}

