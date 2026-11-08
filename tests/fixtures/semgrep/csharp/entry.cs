// ruleid: dossier.csharp.entry.minimal-route
app.MapGet("/health", () => "ok");
// ruleid: dossier.csharp.entry.minimal-route
api.MapPost("/orders", (Order o) => o);
// ruleid: dossier.csharp.entry.minimal-route
app.MapMethods("/x", new[] { "GET" }, handler);
// ruleid: dossier.csharp.entry.minimal-route
app.Map("/y", handler);
// ok: dossier.csharp.entry.minimal-route
cache.Get("x");
// ok: dossier.csharp.entry.minimal-route
dict.Map(x);
// ok: dossier.csharp.entry.minimal-route
app.MapGet(path, handler);

// ruleid: dossier.csharp.entry.fallback-route
app.MapFallback(handler);
// ok: dossier.csharp.entry.fallback-route
app.Fallback(handler);

// ruleid: dossier.csharp.entry.map-hub
app.MapHub<ChatHub>("/chat");
// ok: dossier.csharp.entry.map-hub
app.MapHubs();

// ruleid: dossier.csharp.entry.map-grpc
app.MapGrpcService<Greeter>();
// ok: dossier.csharp.entry.map-grpc
app.MapGrpc();

// ruleid: dossier.csharp.entry.add-hosted
builder.Services.AddHostedService<Cleanup>();
// ok: dossier.csharp.entry.add-hosted
builder.Services.AddSingleton<Cleanup>();

// ruleid: dossier.csharp.entry.hangfire
RecurringJob.AddOrUpdate("nightly", () => Run(), Cron.Daily);
// ruleid: dossier.csharp.entry.hangfire
RecurringJob.AddOrUpdate<Mailer>("mail", m => m.Send(), Cron.Hourly);
// ok: dossier.csharp.entry.hangfire
BackgroundJob.Enqueue(() => Run());

// ruleid: dossier.csharp.entry.cli-command
var root = new Command("serve", "Starts it");
// ruleid: dossier.csharp.entry.cli-command
config.AddCommand<ServeCommand>("serve");
// ok: dossier.csharp.entry.cli-command
var other = new Option("--x");

// ruleid: dossier.csharp.entry.bullseye-target
Target("default", () => Run());
// ok: dossier.csharp.entry.bullseye-target
Targets("x");

// ruleid: dossier.csharp.entry.cli-command
[Verb("add")]
class AddOptions { }
// ok: dossier.csharp.entry.cli-command
[Serializable]
class Plain { }
