namespace Shop.Core;

public class Order // @model-order
{
    public int Id { get; set; }
    public OrderStatus Status { get; set; }
    public int CustomerId { get; set; }
    public Customer? Customer { get; set; }
}
