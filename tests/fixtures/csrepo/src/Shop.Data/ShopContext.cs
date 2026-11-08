using Shop.Core;

namespace Shop.Data;

public class ShopContext(IConfiguration config) : DbContext // @model-ctx
{
    public DbSet<Order> Orders => Set<Order>();
    public DbSet<Customer> Customers => Set<Customer>();

    protected override void OnConfiguring(DbContextOptionsBuilder options)
    {
        options.UseSqlite(config.GetConnectionString("Shop")); // @io-db-connect @io-connstr
    }
}
