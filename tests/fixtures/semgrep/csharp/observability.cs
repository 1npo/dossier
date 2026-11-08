// ruleid: dossier.csharp.observability.log
logger.LogInformation("started {Id}", id);
// ruleid: dossier.csharp.observability.log
_log.LogError(ex, "failed");
// ruleid: dossier.csharp.observability.log
Log.Information("up");
// ruleid: dossier.csharp.observability.log
var cfg = new LoggerConfiguration();
// ruleid: dossier.csharp.observability.log
host.UseSerilog();
// ok: dossier.csharp.observability.log
logger.ToString();
// ok: dossier.csharp.observability.log
catalog.LogInformation("x");

// ruleid: dossier.csharp.observability.metric
var meter = new Meter("shop");
// ruleid: dossier.csharp.observability.metric
var orders = meter.CreateCounter<int>("orders");
// ok: dossier.csharp.observability.metric
var counter = new Counter();

// ruleid: dossier.csharp.observability.trace
var source = new ActivitySource("shop");
// ruleid: dossier.csharp.observability.trace
using var a = source.StartActivity("work");
// ruleid: dossier.csharp.observability.trace
builder.Services.AddOpenTelemetry();
// ok: dossier.csharp.observability.trace
var act = new Action(Run);
