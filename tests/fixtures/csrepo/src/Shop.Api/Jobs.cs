namespace Shop.Api;

public class Jobs
{
    public void Schedule() => RecurringJob.AddOrUpdate("nightly", () => Run(), Cron.Daily); // @ep-cron

    public void Run() { }
}

class MailConsumer : IConsumer<OrderPlaced> // @ep-queue
{
    public Task Consume(ConsumeContext<OrderPlaced> context) => Task.CompletedTask;
}
