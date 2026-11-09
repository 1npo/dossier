import cs_models


def prop(name, type_, attrs=(), mods=("public",), line=5, get=True, static=False):
    return {"name": name, "kind": "property", "modifiers": list(mods), "line": line, "end_line": line, "attributes": [{"name": a, "args": "", "line": line} for a in attrs],
            "type": type_, "static": static, "params": [], "get": get}


def typ(name, members=(), bases=(), attrs=(), kind="class", ns="Shop.Core", line=3, mods=("public",)):
    return {"name": name, "kind": kind, "modifiers": list(mods), "line": line, "end_line": line + 20, "attributes": list(attrs), "bases": list(bases),
            "partial": False, "outer": None, "namespace": ns, "params": [], "members": list(members)}


def d(*types, usings=()):
    return {"namespaces": [], "usings": [{"name": u, "global": False, "static": False, "alias": None} for u in usings], "types": list(types), "top_level": False,
            "idents": {}, "qualified": [], "assembly_attributes": []}


def attr(name, args=""):
    return {"name": name, "args": args, "line": 1}


ORDER = typ("Order", [prop("Id", "int"), prop("Status", "OrderStatus"), prop("CustomerId", "int"), prop("Customer", "Customer?"), prop("Secret", "string", mods=("private",))], line=3)
CUSTOMER = typ("Customer", [prop("Id", "int"), prop("Orders", "ICollection<Order>")], line=3)
STATUS = typ("OrderStatus", [{"name": "New", "kind": "enum-member", "modifiers": [], "line": 5, "end_line": 5, "attributes": [], "type": None, "static": False, "params": []},
                              {"name": "Paid", "kind": "enum-member", "modifiers": [], "line": 6, "end_line": 6, "attributes": [], "type": None, "static": False, "params": []}], kind="enum")
CTX = typ("ShopContext", [{"name": "Orders", "kind": "property", "modifiers": ["public"], "line": 5, "end_line": 5, "attributes": [], "type": "DbSet<Order>", "static": False, "params": [], "get": True},
                          {"name": "Customers", "kind": "property", "modifiers": ["public"], "line": 6, "end_line": 6, "attributes": [], "type": "DbSet<Customer>", "static": False, "params": [], "get": True}],
          bases=["DbContext"], ns="Shop.Data")
DTO = typ("OrderDto", kind="record", ns="Shop.Data")


def items(table, **kw):
    return cs_models.model_items(table, {"projects": []}, **kw)


def by_name(rows):
    return {(i["kind"], i["name"]): i for i in rows}


BASE = {"Core/Order.cs": d(ORDER), "Core/Customer.cs": d(CUSTOMER), "Core/OrderStatus.cs": d(STATUS), "Data/ShopContext.cs": d(CTX, usings=["Shop.Core"]), "Data/OrderDto.cs": d(DTO)}


class TestEfEntities:
    def test_dbset_properties_name_the_entities_and_dtos_are_left_out(self):
        got = by_name(items(BASE))

        assert sorted(got) == [("cs-enum", "OrderStatus"), ("ef-entity", "Customer"), ("ef-entity", "Order")]

    def test_fields_are_the_public_readable_properties_with_keys_and_relations(self):
        order = by_name(items(BASE))[("ef-entity", "Order")]

        assert [(f["name"], f["type"], f["pk"], f["ref"], f["many"]) for f in order["fields"]] == [
            ("Id", "int", True, None, False), ("Status", "OrderStatus", False, "OrderStatus", False), ("CustomerId", "int", False, None, False),
            ("Customer", "Customer", False, "Customer", False)]
        assert order["relations"] == [{"field": "Customer", "to": "Customer", "kind": "ef"}]
        assert (order["rule"], order["path"], order["line"]) == ("cs.ef-entity", "Core/Order.cs", 3)

    def test_a_collection_property_is_many_and_joins_its_element(self):
        customer = by_name(items(BASE))[("ef-entity", "Customer")]

        assert [(f["name"], f["ref"], f["many"]) for f in customer["fields"] if f["name"] == "Orders"] == [("Orders", "Order", True)]
        assert customer["relations"] == [{"field": "Orders", "to": "Order", "kind": "ef"}]

    def test_the_enum_has_its_members_as_fields(self):
        status = by_name(items(BASE))[("cs-enum", "OrderStatus")]

        assert [f["name"] for f in status["fields"]] == ["New", "Paid"] and status["relations"] == []

    def test_a_key_attribute_and_the_type_name_id_are_primary_keys(self):
        thing = typ("Thing", [prop("Code", "string", attrs=["Key"]), prop("ThingId", "int"), prop("Name", "string")])
        table = {**BASE, "Core/Thing.cs": d(thing), "Data/ShopContext.cs": d(typ("ShopContext", [{**CTX["members"][0], "type": "DbSet<Thing>"}], bases=["DbContext"], ns="Shop.Data"), usings=["Shop.Core"])}

        got = by_name(items(table))[("ef-entity", "Thing")]

        assert [(f["name"], f["pk"]) for f in got["fields"]] == [("Code", True), ("ThingId", True), ("Name", False)]

    def test_an_entity_named_only_by_a_configuration_class_is_found(self):
        cfg = typ("OrderConfiguration", bases=["IEntityTypeConfiguration<Order>"], ns="Shop.Data")
        table = {"Core/Order.cs": d(ORDER), "Core/OrderStatus.cs": d(STATUS), "Data/Cfg.cs": d(cfg, usings=["Shop.Core"])}

        assert ("ef-entity", "Order") in by_name(items(table))

    def test_an_entity_named_only_by_modelbuilder_entity_is_found(self):
        ctx = typ("ShopContext", bases=["DbContext"], ns="Shop.Data")
        table = {"Core/Order.cs": d(ORDER), "Core/OrderStatus.cs": d(STATUS), "Data/Ctx.cs": d(ctx, usings=["Shop.Core"])}
        texts = {"Data/Ctx.cs": "protected override void OnModelCreating(ModelBuilder mb) { mb.Entity<Order>(e => { }); }"}

        assert ("ef-entity", "Order") in by_name(items(table, read=texts.get))

    def test_a_context_that_derives_from_another_context_still_counts(self):
        sub = typ("SubContext", [CTX["members"][0]], bases=["ShopContext"], ns="Shop.Data")
        table = {"Core/Order.cs": d(ORDER), "Core/OrderStatus.cs": d(STATUS), "Data/Ctx.cs": d(typ("ShopContext", bases=["IdentityDbContext<User>"], ns="Shop.Data"), sub, usings=["Shop.Core"])}

        assert ("ef-entity", "Order") in by_name(items(table))

    def test_a_dbset_of_a_type_not_in_the_repository_is_ignored(self):
        ctx = typ("C", [{**CTX["members"][0], "type": "DbSet<Missing>"}], bases=["DbContext"])

        assert items({"a.cs": d(ctx)}) == []

    def test_the_relation_picks_the_visible_type_when_another_has_the_same_name(self):
        other = typ("Customer", [prop("X", "int")], ns="Elsewhere")
        table = {**BASE, "Other/Customer.cs": d(other)}

        order = by_name(items(table))[("ef-entity", "Order")]
        customers = [i for i in items(table) if i["name"] == "Customer"]

        assert [f["ref"] for f in order["fields"] if f["name"] == "Customer"] == ["Customer"]
        assert [c["path"] for c in customers] == ["Core/Customer.cs"]

    def test_properties_of_a_base_class_in_the_repository_are_attached_to_the_entity(self):
        base = typ("Entity", [prop("Id", "int"), prop("Created", "DateTime")])
        thing = typ("Thing", [prop("Name", "string")], bases=["Entity"])
        table = {"Core/b.cs": d(base), "Core/t.cs": d(thing), "Data/c.cs": d(typ("C", [{**CTX["members"][0], "type": "DbSet<Thing>"}], bases=["DbContext"]), usings=["Shop.Core"])}

        got = by_name(items(table))[("ef-entity", "Thing")]

        assert [f["name"] for f in got["fields"]] == ["Name", "Id", "Created"] and got["path"] == "Core/t.cs"


class TestOtherKinds:
    def test_owned_types_by_attribute_and_by_call(self):
        addr = typ("Address", [prop("City", "string")], attrs=[attr("Owned")])
        money = typ("Money", [prop("Amount", "decimal")])
        ctx = typ("C", bases=["DbContext"])
        texts = {"c.cs": "b.OwnsOne<Money>(o => o.Total);"}

        got = by_name(items({"a.cs": d(addr), "m.cs": d(money), "c.cs": d(ctx)}, read=texts.get))

        assert ("ef-owned", "Address") in got and ("ef-owned", "Money") in got

    def test_dapper_row_and_table_class(self):
        product = typ("Product", [prop("Id", "int")])
        legacy = typ("Legacy", [prop("Id", "int")], attrs=[attr("Table", '"legacy"')])
        reports = typ("Reports", ns="Shop.Data")
        texts = {"r.cs": 'conn.Query<Product>("select 1"); await conn.QueryFirstOrDefaultAsync<Product>("x");'}

        got = by_name(items({"p.cs": d(product), "l.cs": d(legacy), "r.cs": d(reports, usings=["Shop.Core"])}, read=texts.get))

        assert sorted(got) == [("dapper-row", "Product"), ("table-class", "Legacy")]

    def test_an_entity_is_not_also_a_dapper_row(self):
        texts = {"Data/ShopContext.cs": "conn.Query<Order>(sql);"}

        got = [i for i in items(BASE, read=texts.get) if i["name"] == "Order"]

        assert [i["kind"] for i in got] == ["ef-entity"]

    def test_query_of_a_type_not_declared_in_the_repository_gives_nothing(self):
        assert items({"r.cs": d(typ("R"))}, read={"r.cs": "c.Query<Unknown>(x);"}.get) == []

    def test_a_generated_file_is_not_an_entity(self):
        assert items(BASE, generated={"Core/Order.cs"}) and ("ef-entity", "Order") not in by_name(items(BASE, generated={"Core/Order.cs"}))


class TestMigrations:
    def test_a_migration_and_a_snapshot(self):
        mig = typ("Init", bases=["Migration"], attrs=[attr("Migration", '"20260101000000_Init"')], ns="D.M", mods=("public", "partial"))
        snap = typ("ShopContextModelSnapshot", bases=["ModelSnapshot"], ns="D.M")

        got = items({"m/Init.cs": d(mig), "m/Snap.cs": d(snap)})

        assert got == [{"path": "m/Init.cs", "line": 3, "kind": "migration", "tool": "ef-core", "name": "20260101000000_Init", "rule": "cs.migration"},
                       {"path": "m/Snap.cs", "line": 3, "kind": "migration", "tool": "ef-core", "name": "ShopContextModelSnapshot", "snapshot": True, "rule": "cs.migration"}]

    def test_a_class_with_the_attribute_but_another_base_is_not_a_migration(self):
        assert items({"m.cs": d(typ("X", bases=["Other"], attrs=[attr("Migration", '"1"')]))}) == []
