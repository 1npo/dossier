namespace Shop.Core;

public static class Money
{
    public static decimal Round(decimal value) => Math.Round(value, 2); // @api-method

    public static decimal Round(decimal value, int places) => Math.Round(value, places);

    public static string Shout(this string s) => s.ToUpperInvariant(); // @api-ext
}
