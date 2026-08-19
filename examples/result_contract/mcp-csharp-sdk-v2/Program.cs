using System.IO.Pipelines;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using ModelContextProtocol.Client;
using ModelContextProtocol.Protocol;
using ModelContextProtocol.Server;

const string PackageVersion = "2.2.0";
const string ProtocolVersion = "2026-07-28";
const string ToolName = "qzx_reference_lookup";

if (args.Length != 2)
{
    throw new ArgumentException(
        "Usage: <canonical-schema-path> <evidence-directory>");
}

string schemaPath = Path.GetFullPath(args[0]);
string evidenceDirectory = Path.GetFullPath(args[1]);
Directory.CreateDirectory(evidenceDirectory);

using JsonDocument schemaDocument = JsonDocument.Parse(
    await File.ReadAllTextAsync(schemaPath));
JsonElement canonicalSchema = schemaDocument.RootElement.Clone();

McpServerTool tool = McpServerTool.Create(
    (bool fail) => CreateResult(fail),
    new McpServerToolCreateOptions
    {
        Name = ToolName,
        Description = "Return one synthetic QZX Result Contract reference result.",
        UseStructuredContent = true,
        OutputSchema = canonicalSchema,
        ReadOnly = true,
        Idempotent = true,
        OpenWorld = false,
    });

Pipe clientToServer = new();
Pipe serverToClient = new();
await using McpServer server = McpServer.Create(
    new StreamServerTransport(
        clientToServer.Reader.AsStream(),
        serverToClient.Writer.AsStream()),
    new McpServerOptions
    {
        ProtocolVersion = ProtocolVersion,
        ServerInfo = new Implementation
        {
            Name = "qzx-csharp-reference-server",
            Version = "1.0.0",
        },
        ToolCollection = [tool],
    });

Task serverTask = server.RunAsync();
await using McpClient client = await McpClient.CreateAsync(
    new StreamClientTransport(
        clientToServer.Writer.AsStream(),
        serverToClient.Reader.AsStream()),
    new McpClientOptions
    {
        ProtocolVersion = ProtocolVersion,
        ClientInfo = new Implementation
        {
            Name = "qzx-csharp-reference-client",
            Version = "1.0.0",
        },
    });

if (client.NegotiatedProtocolVersion != ProtocolVersion)
{
    throw new InvalidOperationException(
        $"Expected MCP {ProtocolVersion}, received " +
        $"{client.NegotiatedProtocolVersion}.");
}

IList<McpClientTool> tools = await client.ListToolsAsync();
McpClientTool listedTool = tools.Single(candidate => candidate.Name == ToolName);
if (listedTool.ProtocolTool.OutputSchema is not JsonElement advertisedSchema ||
    !JsonElement.DeepEquals(canonicalSchema, advertisedSchema))
{
    throw new InvalidOperationException(
        "The official SDK changed the canonical inline output schema.");
}

CallToolResult success = await listedTool.CallAsync(
    new Dictionary<string, object?> { ["fail"] = false });
CallToolResult failure = await listedTool.CallAsync(
    new Dictionary<string, object?> { ["fail"] = true });

AssertResult(success, expectedSuccess: true);
AssertResult(failure, expectedSuccess: false);

JsonSerializerOptions wireOptions = new()
{
    WriteIndented = true,
    NewLine = "\n",
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
};

await WriteJsonAsync(
    Path.Combine(evidenceDirectory, "tool-definition.json"),
    listedTool.ProtocolTool,
    wireOptions);
await WriteJsonAsync(
    Path.Combine(evidenceDirectory, "success.json"),
    success,
    wireOptions);
await WriteJsonAsync(
    Path.Combine(evidenceDirectory, "failure.json"),
    failure,
    wireOptions);

Dictionary<string, string> evidenceSha256 = new(StringComparer.Ordinal)
{
    ["tool-definition.json"] = Sha256(
        Path.Combine(evidenceDirectory, "tool-definition.json")),
    ["success.json"] = Sha256(Path.Combine(evidenceDirectory, "success.json")),
    ["failure.json"] = Sha256(Path.Combine(evidenceDirectory, "failure.json")),
};
Dictionary<string, string> expectedSha256 = new(StringComparer.Ordinal)
{
    ["tool-definition.json"] =
        "cc32c0e1f9648e66cb81c1fc28862014b660d4714a477ec75316352367db273c",
    ["success.json"] =
        "9fa166682624f3f8dc4c7984f9ff9630287994fea8e78774a3e5df01bbc92cd2",
    ["failure.json"] =
        "34330cf5f34f38de7667f3ae9e6f2923aec9f519e56d46a6918a0e8a8cb4fee7",
};
foreach ((string filename, string expected) in expectedSha256)
{
    if (evidenceSha256[filename] != expected)
    {
        throw new InvalidOperationException(
            $"{filename} changed from expected SHA-256 {expected} to " +
            $"{evidenceSha256[filename]}.");
    }
}

AssemblyName sdkAssembly = typeof(McpClient).Assembly.GetName();
string assemblyVersion = sdkAssembly.Version?.ToString() ?? "unknown";
if (!assemblyVersion.StartsWith($"{PackageVersion}.", StringComparison.Ordinal))
{
    throw new InvalidOperationException(
        $"Expected SDK assembly {PackageVersion}.x, received {assemblyVersion}.");
}

await WriteJsonAsync(
    Path.Combine(evidenceDirectory, "evidence-metadata.json"),
    new
    {
        evidence_kind = "qzx_maintained_reference",
        independent_adoption = false,
        sdk = "modelcontextprotocol/csharp-sdk",
        package = "ModelContextProtocol.Core",
        package_version = PackageVersion,
        assembly_version = assemblyVersion,
        protocol_version = client.NegotiatedProtocolVersion,
        target_framework = "net10.0",
        runtime = System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription,
        operating_system = System.Runtime.InteropServices.RuntimeInformation.OSDescription,
        transport = "in_process_newline_delimited_json_rpc_streams",
        jsonrpc_framing_exercised = true,
        wire_capture_retained = false,
        http_exercised = false,
        sse_exercised = false,
        output_schema_mode = "canonical_inline",
        contract_evidence_sha256 = evidenceSha256,
        tool = ToolName,
    },
    wireOptions);

await client.DisposeAsync();
await server.DisposeAsync();
await serverTask;

static CallToolResult CreateResult(bool fail)
{
    JsonElement structured = fail
        ? JsonSerializer.SerializeToElement(new
        {
            success = false,
            message = "Synthetic lookup rejected the requested item.",
            error = "The synthetic item does not exist.",
            error_code = "item_not_found",
            details = new
            {
                item = "missing-item",
                source = "csharp-sdk-v2.2.0",
            },
        })
        : JsonSerializer.SerializeToElement(new
        {
            success = true,
            message = "Synthetic lookup returned the requested item.",
            details = new
            {
                item = "example-item",
                value = 42,
                source = "csharp-sdk-v2.2.0",
            },
        });

    return new CallToolResult
    {
        Content = [new TextContentBlock { Text = structured.GetRawText() }],
        StructuredContent = structured,
        IsError = fail,
    };
}

static void AssertResult(CallToolResult result, bool expectedSuccess)
{
    if (result.ResultType != "complete")
    {
        throw new InvalidOperationException(
            "The official SDK did not retain resultType=complete.");
    }

    JsonElement structured = result.StructuredContent ??
        throw new InvalidOperationException(
            "The official SDK omitted structuredContent.");
    bool actualSuccess = structured.GetProperty("success").GetBoolean();
    if (actualSuccess != expectedSuccess || result.IsError != !expectedSuccess)
    {
        throw new InvalidOperationException(
            "The official SDK observed an inconsistent result pair.");
    }

    string text = result.Content.OfType<TextContentBlock>().Single().Text;
    using JsonDocument textDocument = JsonDocument.Parse(text);
    if (!JsonElement.DeepEquals(textDocument.RootElement, structured))
    {
        throw new InvalidOperationException(
            "The compatibility text does not match structuredContent.");
    }
}

static async Task WriteJsonAsync<T>(
    string path,
    T value,
    JsonSerializerOptions options)
{
    string serialized = JsonSerializer.Serialize(value, options) + "\n";
    await File.WriteAllTextAsync(path, serialized);
}

static string Sha256(string path)
{
    byte[] digest = SHA256.HashData(File.ReadAllBytes(path));
    return Convert.ToHexString(digest).ToLowerInvariant();
}
