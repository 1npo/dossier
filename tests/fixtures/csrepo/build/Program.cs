using static Bullseye.Targets;

Target("default", () => Console.WriteLine("build")); // @ep-target
Target("test", () => Console.WriteLine("test"));
await RunTargetsAndExitAsync(args);
