// ruleid: dossier.csharp.concurrency.thread
var t = new Thread(Run);
// ruleid: dossier.csharp.concurrency.thread
ThreadPool.QueueUserWorkItem(_ => Run());
// ok: dossier.csharp.concurrency.thread
var th = new ThreadStaticAttribute();

// ruleid: dossier.csharp.concurrency.async
await Task.Run(() => Work());
// ruleid: dossier.csharp.concurrency.async
await Task.WhenAll(a, b);
// ruleid: dossier.csharp.concurrency.async
Parallel.ForEach(items, Work);
// ruleid: dossier.csharp.concurrency.async
using var timer = new PeriodicTimer(TimeSpan.FromMinutes(5));
// ok: dossier.csharp.concurrency.async
await Task.Delay(10);

// ruleid: dossier.csharp.concurrency.lock
lock (gate) { count++; }
// ruleid: dossier.csharp.concurrency.lock
var sem = new SemaphoreSlim(1);
// ruleid: dossier.csharp.concurrency.lock
Interlocked.Increment(ref count);
// ok: dossier.csharp.concurrency.lock
var gate2 = new object();

// ruleid: dossier.csharp.concurrency.queue
var ch = Channel.CreateUnbounded<int>();
// ruleid: dossier.csharp.concurrency.queue
var q = new ConcurrentQueue<int>();
// ok: dossier.csharp.concurrency.queue
var plain = new Queue<int>();

// ruleid: dossier.csharp.concurrency.process-pool
Process.Start("ls");
// ok: dossier.csharp.concurrency.process-pool
Process.GetCurrentProcess();
