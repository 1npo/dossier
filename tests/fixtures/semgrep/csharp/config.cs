// ruleid: dossier.csharp.config.config-key
var key1 = builder.Configuration["Shop:Name"];
// ruleid: dossier.csharp.config.config-key
var key2 = config.GetValue<int>("Shop:Port", 80);
// ruleid: dossier.csharp.config.config-key
var key3 = config.GetSection("Shop");
// ruleid: dossier.csharp.config.config-key
var key4 = config.GetRequiredSection("Shop:Db");
// ruleid: dossier.csharp.config.config-key
var key5 = config.GetConnectionString("Shop");
// ruleid: dossier.csharp.config.config-key, dossier.csharp.config.config-binding
services.AddOptions<ShopOptions>().BindConfiguration("Shop");
// ok: dossier.csharp.config.config-key
var key6 = lookup["Shop:Name"];
// ok: dossier.csharp.config.config-key
var key7 = config.GetValue<int>(name);

// ruleid: dossier.csharp.config.config-binding
services.Configure<ShopOptions>(options);
// ruleid: dossier.csharp.config.config-binding
services.AddOptions<ShopOptions>();
// ruleid: dossier.csharp.config.config-binding
var opts = section.Get<ShopOptions>();
// ruleid: dossier.csharp.config.config-binding
config.Bind(shopOptions);
// ok: dossier.csharp.config.config-binding
var list = items.Get<ShopOptions>();
// ok: dossier.csharp.config.config-binding
var other = IList<ShopOptions>.Empty;

public class ShopService
{
    // ruleid: dossier.csharp.config.config-binding
    public ShopService(IOptions<ShopOptions> options) { }
    // ruleid: dossier.csharp.config.config-binding
    public ShopService(IOptionsMonitor<ShopOptions> options, int n) { }
}
