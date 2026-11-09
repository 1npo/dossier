// ruleid: dossier.csharp.inputs.env-var
var key = Environment.GetEnvironmentVariable("SHOP_KEY");
// ok: dossier.csharp.inputs.env-var
var path = Environment.GetFolderPath(Environment.SpecialFolder.Desktop);

// ruleid: dossier.csharp.inputs.config-file
var name = builder.Configuration["Shop:Name"];
// ruleid: dossier.csharp.inputs.config-file
var port = config.GetValue<int>("Port");
// ruleid: dossier.csharp.inputs.config-file
var section = config.GetSection("Shop");
// ruleid: dossier.csharp.inputs.config-file
var cs = config.GetConnectionString("Shop");
// ruleid: dossier.csharp.inputs.config-file
services.Configure<ShopOptions>(config);
// ruleid: dossier.csharp.inputs.config-file
builder.AddJsonFile("extra.json");
// ruleid: dossier.csharp.inputs.config-file
builder.AddEnvironmentVariables();
// ok: dossier.csharp.inputs.config-file
var item = lookup["Shop:Name"];

// ruleid: dossier.csharp.inputs.cli-args
var all = Environment.GetCommandLineArgs();
// ruleid: dossier.csharp.inputs.cli-args
var b = WebApplication.CreateBuilder(args);
// ruleid: dossier.csharp.inputs.cli-args
var first = args[0];
// ok: dossier.csharp.inputs.cli-args
var c = WebApplication.CreateBuilder();

// ruleid: dossier.csharp.inputs.file-read
var text = File.ReadAllText("a.txt");
// ruleid: dossier.csharp.inputs.file-read
using var reader = new StreamReader(stream);
// ruleid: dossier.csharp.inputs.file-read
app.UseStaticFiles();
// ok: dossier.csharp.inputs.file-read
File.WriteAllText("a.txt", "x");

// ruleid: dossier.csharp.inputs.stdin
var line = Console.ReadLine();
// ruleid: dossier.csharp.inputs.stdin
var key2 = Console.ReadKey(true);
// ok: dossier.csharp.inputs.stdin
Console.WriteLine("x");

// ruleid: dossier.csharp.inputs.request-header
var tenant = request.Headers["X-Tenant"];
// ruleid: dossier.csharp.inputs.request-header
public IActionResult Get([FromHeader(Name = "X-Trace")] string trace) => Ok();
// ok: dossier.csharp.inputs.request-header
var h = response.Content["X-Tenant"];
