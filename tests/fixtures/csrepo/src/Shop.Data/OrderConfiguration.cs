namespace Shop.Data;

public class OrderConfiguration : IEntityTypeConfiguration<Order>
{
    public void Configure(EntityTypeBuilder<Order> builder) => builder.HasKey(o => o.Id);
}
