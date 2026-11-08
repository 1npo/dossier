namespace Shop.Api;

public static class Plugins
{
    public static object? Make(Type t) => Activator.CreateInstance(t); // @bs-reflect

    public static Type[] All(Assembly asm) => asm.GetTypes();
}
