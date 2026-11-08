namespace Shop.Data;

public class Reports(IDbConnection conn)
{
    public IEnumerable<Product> All() => conn.Query<Product>("select * from products"); // @model-dapper @io-dapper
}
