using System.Diagnostics;

class Program
{
    static void Main(string[] args) // @ep-main
    {
        var first = args[0]; // @io-args
        var line = Console.ReadLine(); // @io-stdin
        var cmd = new Command("sync"); // @ep-cli
        Process.Start("git"); // @cc-process
        Environment.Exit(2); // @io-exit
    }
}
