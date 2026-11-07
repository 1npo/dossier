import js_prisma

SCHEMA = '''datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}

model User {
  id    Int    @id @default(autoincrement())
  email String @unique
  role  Role   @default(USER)
  posts Post[]
  boss  User?  @relation("boss", fields: [bossId], references: [id])
  bossId Int?
}

model Post {
  id       Int    @id
  title    String
  author   User   @relation(fields: [authorId], references: [id])
  authorId Int

  @@index([authorId])
}

model Link {
  a Int
  b Int
  @@id([a, b])
}

enum Role {
  USER
  ADMIN
  Low = "low"
}
'''


def models():
    return {m["name"]: m for m in js_prisma.parse("prisma/schema.prisma", SCHEMA)["models"]}


class TestParseModels:
    def test_models_and_enums_come_with_their_kinds_and_lines(self):
        got = models()

        assert [(n, m["kind"], m["line"]) for n, m in got.items()] == [("User", "prisma", 10), ("Post", "prisma", 19), ("Link", "prisma", 28), ("Role", "prisma-enum", 34)]
        assert got["User"]["end_line"] == 17

    def test_the_id_attribute_marks_a_primary_key(self):
        fields = {f["name"]: f for f in models()["User"]["fields"]}

        assert fields["id"]["pk"] is True and fields["email"]["pk"] is False

    def test_a_composite_id_marks_each_named_field(self):
        assert [f["name"] for f in models()["Link"]["fields"] if f["pk"]] == ["a", "b"]

    def test_refs_follow_arrays_and_optionals_to_models_and_enums(self):
        fields = {f["name"]: f["ref"] for f in models()["User"]["fields"]}

        assert (fields["posts"], fields["boss"], fields["role"], fields["email"]) == ("Post", "User", "Role", None)

    def test_a_field_that_points_at_another_model_has_a_ref(self):
        assert {f["name"]: f["ref"] for f in models()["Post"]["fields"]}["author"] == "User"

    def test_a_block_attribute_line_is_not_a_field(self):
        assert "@@index" not in [f["name"] for f in models()["Post"]["fields"]]

    def test_an_enum_member_with_a_value_is_a_member(self):
        assert [f["name"] for f in models()["Role"]["fields"]] == ["USER", "ADMIN", "Low"]


class TestParseIo:
    def test_env_call_gives_an_env_var_and_the_datasource_a_db_connect(self):
        io = js_prisma.parse("prisma/schema.prisma", SCHEMA)["io"]

        assert [(i["category"], i["name"], i["detail"], i["line"]) for i in io] == [("db-connect", "db", "postgresql", 1), ("env-var", "DATABASE_URL", "DATABASE_URL", 3)]

    def test_a_file_with_no_blocks_gives_nothing(self):
        assert js_prisma.parse("a.prisma", "// nothing\n") == {"models": [], "io": []}
