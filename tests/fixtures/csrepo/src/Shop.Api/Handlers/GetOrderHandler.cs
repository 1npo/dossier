namespace Shop.Api.Handlers;

public class GetOrderHandler : IRequestHandler<GetOrder, Order> // @bs-handler
{
    public Task<Order> Handle(GetOrder request, CancellationToken ct) => Task.FromResult(new Order());
}
