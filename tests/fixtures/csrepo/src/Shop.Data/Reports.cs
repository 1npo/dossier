using Shop.Core.Models;
using Shop.Data.Models;

namespace Shop.Data;

public class Reports(IDbConnection conn)
{
    public IEnumerable<Product> All() => conn.Query<Product>("select * from products"); // @model-dapper @io-dapper

    public Item Pick() => null!; // @name-ambiguous
}

public class Product
{
    public int Id { get; set; }
    public string Title { get; set; } = "";
}
