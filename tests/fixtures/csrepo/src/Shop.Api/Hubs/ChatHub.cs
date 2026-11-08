namespace Shop.Api.Hubs;

public class ChatHub : Hub
{
    public Task Say(string text) => Clients.All.SendAsync("said", text);
}
