namespace Shop.Core;

public class Customer
{
    public int Id { get; set; }
    public ICollection<Order> Orders { get; set; } = new List<Order>(); // @model-customer
}
