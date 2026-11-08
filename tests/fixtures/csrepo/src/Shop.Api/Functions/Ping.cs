namespace Shop.Api.Functions;

public class Ping
{
    [Function("Ping")]
    public string Run([HttpTrigger(AuthorizationLevel.Anonymous, "get")] string req) => "pong"; // @ep-func

    [Function("Tick")]
    public void Tick([TimerTrigger("0 */5 * * * *")] string timer) { } // @ep-func-timer
}
