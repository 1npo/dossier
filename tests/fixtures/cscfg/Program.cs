using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Options;

var builder = WebApplication.CreateBuilder(args);
builder.Services.Configure<ShopOptions>(builder.Configuration.GetSection("Shop"));
var name = builder.Configuration["Shop:Name"];
var cs = builder.Configuration.GetConnectionString("Db");
var lookup = new Dictionary<string, string>();
var other = lookup["Shop:Name"];

public class ShopOptions { public string Name { get; set; } }

public class Greeter
{
    public Greeter(IOptions<ShopOptions> options) { }
}
