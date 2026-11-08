// ruleid: dossier.csharp.state.db-connect
options.UseSqlite(config.GetConnectionString("Shop"));
// ruleid: dossier.csharp.state.db-connect
options.UseNpgsql("Host=x");
// ruleid: dossier.csharp.state.db-connect
builder.Services.AddDbContext<ShopContext>(o => o.UseInMemoryDatabase("x"));
// ruleid: dossier.csharp.state.db-connect
var conn = new SqlConnection(cs);
// ruleid: dossier.csharp.state.db-connect
var mux = ConnectionMultiplexer.Connect("localhost");
// ok: dossier.csharp.state.db-connect
var x = new Connection(cs);

// ruleid: dossier.csharp.state.db-access
await db.SaveChangesAsync();
// ruleid: dossier.csharp.state.db-access
var all = ctx.Set<Order>();
// ruleid: dossier.csharp.state.db-access
var rows = ctx.Orders.FromSqlRaw("select 1");
// ruleid: dossier.csharp.state.db-access
var many = conn.Query<Product>("select 1");
// ruleid: dossier.csharp.state.db-access
_db.Orders.Add(order);
// ruleid: dossier.csharp.state.db-access
dbContext.Orders.Remove(order);
// ok: dossier.csharp.state.db-access
items.Add(x);
// ok: dossier.csharp.state.db-access
list.Orders.Add(x);
// ok: dossier.csharp.state.db-access
var q = parser.Query("x");

// ruleid: dossier.csharp.state.cache
builder.Services.AddMemoryCache();
// ruleid: dossier.csharp.state.cache
var v = await cache.GetOrCreateAsync("k", e => load());
// ruleid: dossier.csharp.state.cache
_cache.Set("k", value);
// ok: dossier.csharp.state.cache
var h = hash.Set("k", value);
// ok: dossier.csharp.state.cache
var s = settings.GetOrCreate("k");
