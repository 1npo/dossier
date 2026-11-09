namespace Shop.Api.Mapping;

[Mapper] // @bs-generator
public partial class OrderMapper // @bs-partial
{
    public partial OrderDto ToDto(Order order);

    [LoggerMessage(Level = LogLevel.Information, Message = "placed")]
    static partial void LogPlaced(ILogger logger);
}
