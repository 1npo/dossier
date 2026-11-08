namespace Shop.Api.Filters;

public class AuditFilter : IAsyncActionFilter // @bs-filter-class
{
    public Task OnActionExecutionAsync(ActionExecutingContext c, ActionExecutionDelegate next) => next();
}
