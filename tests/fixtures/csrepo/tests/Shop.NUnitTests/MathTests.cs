namespace Shop.NUnitTests;

[TestFixture]
public class MathTests
{
    [SetUp]
    public void Init() { }

    [Test]
    public void Adds() => Assert.That(1 + 1, Is.EqualTo(2));

    [Test]
    [Ignore("x")] // @test-ignore
    public void Skipped() { }
}
