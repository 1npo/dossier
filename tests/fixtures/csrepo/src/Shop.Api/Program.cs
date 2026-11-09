using Serilog;

var builder = WebApplication.CreateBuilder(); // @ep-program
var name = builder.Configuration["Shop:Name"]; // @io-config
var key = Environment.GetEnvironmentVariable("SHOP_KEY"); // @io-env
builder.Services.AddScoped<IOrderService, OrderService>(); // @bs-di
builder.Services.AddMediatR(c => c.RegisterServicesFromAssembly(typeof(Program).Assembly)); // @bs-scan
builder.Services.AddHostedService<Cleanup>(); // @ep-hosted-add
builder.Services.AddHttpClient(); // @io-outbound-add
builder.Services.AddControllers(opt =>
{
    opt.Conventions.Add(new PrefixConvention()); // @bs-convention
    opt.Filters.Add<AuditFilter>(); // @bs-filter
});
var app = builder.Build();
app.UseExceptionHandler("/error"); // @fail-handler
app.MapGet("/health", () => "ok"); // @ep-min-get
var api = app.MapGroup("/api"); // @bs-group
api.MapPost("/orders", (Order o) => o); // @ep-min-post
app.MapGet(path, h); // @bs-route
app.MapControllerRoute("default", "{controller}/{action}"); // @bs-conventional
app.MapHub<ChatHub>("/chat"); // @ep-hub
app.MapGrpcService<Greeter>(); // @ep-grpc
Log.Information("up"); // @io-log
Console.WriteLine("ready"); // @io-stdout
cache.Get("x"); // @not-route
app.Run();
