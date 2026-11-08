// ruleid: dossier.csharp.outputs.stdout
Console.WriteLine("ready");
// ruleid: dossier.csharp.outputs.stdout
Console.Error.WriteLine("bad");
// ok: dossier.csharp.outputs.stdout
logger.WriteLine("x");

// ruleid: dossier.csharp.outputs.file-write
File.WriteAllText("a.txt", "x");
// ruleid: dossier.csharp.outputs.file-write
File.AppendAllText("a.txt", "x");
// ruleid: dossier.csharp.outputs.file-write
using var w = new StreamWriter("a.txt");
// ok: dossier.csharp.outputs.file-write
var t = File.ReadAllText("a.txt");

// ruleid: dossier.csharp.outputs.outbound-call
var c = new HttpClient();
// ruleid: dossier.csharp.outputs.outbound-call
builder.Services.AddHttpClient();
// ruleid: dossier.csharp.outputs.outbound-call
var r = await httpClient.GetAsync("https://x");
// ruleid: dossier.csharp.outputs.outbound-call
var j = await client.PostAsJsonAsync("/x", body);
// ok: dossier.csharp.outputs.outbound-call
var d = await cache.GetAsync("k");

// ruleid: dossier.csharp.outputs.message-produce
await bus.Publish(new OrderPlaced());
// ruleid: dossier.csharp.outputs.message-produce
await producer.ProduceAsync("topic", msg);
// ruleid: dossier.csharp.outputs.message-produce
channel.BasicPublish("", "q", null, body);
// ok: dossier.csharp.outputs.message-produce
list.Send(x);

// ruleid: dossier.csharp.outputs.exit-code
Environment.Exit(1);
// ruleid: dossier.csharp.outputs.exit-code
Environment.ExitCode = 2;
// ok: dossier.csharp.outputs.exit-code
var e = Environment.ProcessId;

// ruleid: dossier.csharp.outputs.error-response
return BadRequest("no");
// ruleid: dossier.csharp.outputs.error-response
return NotFound();
// ruleid: dossier.csharp.outputs.error-response
return StatusCode(500, "x");
// ruleid: dossier.csharp.outputs.error-response
return Results.NotFound();
// ruleid: dossier.csharp.outputs.error-response
return TypedResults.Conflict();
// ruleid: dossier.csharp.outputs.error-response
context.Response.StatusCode = 404;
// ruleid: dossier.csharp.outputs.error-response
throw new NotFoundException("x");
// ruleid: dossier.csharp.outputs.error-response
throw new ApiException("x");
// ok: dossier.csharp.outputs.error-response
return StatusCode(200, "x");
// ok: dossier.csharp.outputs.error-response
context.Response.StatusCode = 200;
// ok: dossier.csharp.outputs.error-response
throw new ArgumentException("x");
// ok: dossier.csharp.outputs.error-response
return Ok();
