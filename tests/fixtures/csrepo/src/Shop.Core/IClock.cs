namespace Shop.Core;

public interface IClock // @api-interface
{
    DateTime Now { get; }
}
