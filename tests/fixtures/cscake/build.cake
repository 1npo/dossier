var target = Argument("target", "Default");
var configuration = Argument("configuration", "Release");

// Task("Commented") is not a task
Task("Clean")
    .Does(() => CleanDirectory("./artifacts"));

Task("Build")
    .IsDependentOn("Clean")
    .Does(() => DotNetBuild("./Shop.sln"));

Task('Test').IsDependentOn("Build")
    .Does(() => DotNetTest("./Shop.sln"));

Task("Default")
    .IsDependentOn("Test");

Setup(ctx => Information("start"));
RunTarget(target);
