namespace Shop.Tests;

public class OrdersTests : IClassFixture<WebApplicationFactory<Program>> // @test-fixture
{
    [Fact]
    public void Adds() => Assert.Equal(2, 1 + 1);

    [Fact]
    public void Subtracts() => Assert.Equal(0, 1 - 1);

    [Fact(Skip = "flaky")] // @test-skip
    public void Flaky() { }

    [Theory]
    [InlineData(1)]
    [InlineData(2)]
    public void Many(int n)
    {
        var clock = new Mock<IClock>(); // @test-mock
        Assert.True(n > 0);
    }
}
