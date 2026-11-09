namespace Shop.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class OrdersController : ControllerBase
{
    [HttpGet] // @ep-ctl-list
    public IActionResult List() => Ok();

    [HttpGet("{id}")] // @ep-ctl-get
    public async Task<IActionResult> Get(int id, [FromHeader(Name = "X-Tenant")] string tenant) // @io-header
    {
        var found = await _mediator.Send(new GetOrder(id)); // @bs-mediator-send
        var clock = HttpContext.RequestServices.GetRequiredService<IClock>(); // @bs-resolve
        return found is null ? NotFound() : Ok(found); // @io-error
    }

    [HttpPost("~/submit")] // @ep-ctl-abs
    public IActionResult Submit(Order order) => Ok(order);
}
