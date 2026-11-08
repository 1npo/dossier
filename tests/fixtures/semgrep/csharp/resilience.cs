// ruleid: dossier.csharp.resilience.retry
builder.AddStandardResilienceHandler();
// ruleid: dossier.csharp.resilience.retry
var policy = Policy.Handle<HttpRequestException>().WaitAndRetryAsync(3, i => TimeSpan.FromSeconds(i));
// ruleid: dossier.csharp.resilience.retry
o.EnableRetryOnFailure(3);
// ok: dossier.csharp.resilience.retry
var again = Retry();

// ruleid: dossier.csharp.resilience.timeout
client.Timeout = TimeSpan.FromSeconds(5);
// ruleid: dossier.csharp.resilience.timeout
cts.CancelAfter(1000);
// ok: dossier.csharp.resilience.timeout
var t = client.TimeoutPolicy;

// ruleid: dossier.csharp.resilience.catch-all
try { Run(); } catch (Exception ex) { Log(ex); }
// ruleid: dossier.csharp.resilience.catch-all
try { Run(); } catch { }
// ruleid: dossier.csharp.resilience.catch-all
app.UseExceptionHandler("/error");
// ruleid: dossier.csharp.resilience.catch-all
AppDomain.CurrentDomain.UnhandledException += OnCrash;
// ok: dossier.csharp.resilience.catch-all
try { Run(); } catch (IOException ex) { Log(ex); }

// ruleid: dossier.csharp.resilience.transaction
using var tx = await db.Database.BeginTransactionAsync();
// ruleid: dossier.csharp.resilience.transaction
using var scope = new TransactionScope();
// ok: dossier.csharp.resilience.transaction
var tx2 = new TransactionOptions();

// ruleid: dossier.csharp.resilience.catch-all
class Handler : IExceptionHandler { }
// ok: dossier.csharp.resilience.catch-all
class Plain : IDisposable { }
