namespace Shop.Api.Services;

public class Cleanup : BackgroundService // @ep-hosted
{
    protected override async Task ExecuteAsync(CancellationToken stop)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromMinutes(5));
        while (await timer.WaitForNextTickAsync(stop)) { }
    }
}
