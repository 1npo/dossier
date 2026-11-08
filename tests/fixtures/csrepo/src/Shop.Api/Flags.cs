namespace Shop.Api;

public class Flags(IFeatureManager features) // @bs-flag
{
    public Task<bool> Beta() => features.IsEnabledAsync("beta");
}
