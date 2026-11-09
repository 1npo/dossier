namespace Shop.Core;

public interface IOrderService
{
    Task Place(Order order, string url);
}
