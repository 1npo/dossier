using Shop.Core;

namespace Shop.Api.Services;

public class OrderService : IOrderService
{
    static int _count; // @state-static
    private static readonly string Name = "x";
    private readonly object _gate = new();
    private readonly HttpClient _http;
    private readonly ShopContext _db;
    private readonly ILogger<OrderService> _logger;
    private readonly IBus _bus;

    public async Task Place(Order o, string url)
    {
        await _http.GetAsync(url); // @io-outbound
        _db.Orders.Add(o); // @io-db
        await _db.SaveChangesAsync(); // @io-db-save
        await _db.Database.BeginTransactionAsync(); // @fail-tx
        try { _count++; }
        catch (Exception ex) // @fail-catch
        {
            _logger.LogWarning("x"); // @io-log2
        }
        var policy = Policy.Handle<HttpRequestException>().WaitAndRetryAsync(3, _ => TimeSpan.Zero); // @fail-retry
        var prices = File.ReadAllText("prices.csv"); // @io-file-read
        File.WriteAllText("out.txt", ""); // @io-file-write
        lock (_gate) // @cc-lock
        {
            _count++;
        }
        await Task.WhenAll(a, b); // @cc-async
        _bus.Publish(new OrderPlaced()); // @io-produce
    }
}
