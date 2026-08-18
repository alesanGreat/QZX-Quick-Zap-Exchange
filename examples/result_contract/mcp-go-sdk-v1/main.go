package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"runtime"
	"runtime/debug"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

const (
	protocolVersion = "2025-11-25"
	toolName        = "lookup_widget"
)

type lookupInput struct {
	Fail bool `json:"fail"`
}

type widgetDetails struct {
	WidgetID string `json:"widget_id"`
	Status   string `json:"status,omitempty"`
}

type resultDocument struct {
	Success   bool          `json:"success"`
	Message   string        `json:"message"`
	ErrorCode string        `json:"error_code,omitempty"`
	Details   widgetDetails `json:"details"`
}

func contractSchemaPath() (string, error) {
	_, source, _, ok := runtime.Caller(0)
	if !ok {
		return "", errors.New("could not locate the Go evidence source")
	}
	return filepath.Clean(filepath.Join(
		filepath.Dir(source),
		"..", "..", "..", "src", "qzx", "resources", "schemas",
		"result-contract-v1.schema.json",
	)), nil
}

func moduleVersion(modulePath string) string {
	info, ok := debug.ReadBuildInfo()
	if !ok {
		return "unavailable"
	}
	for _, dependency := range info.Deps {
		if dependency.Path == modulePath {
			if dependency.Replace != nil {
				return dependency.Replace.Version
			}
			return dependency.Version
		}
	}
	return "unavailable"
}

func writeJSON(path string, document any) error {
	encoded, err := json.MarshalIndent(document, "", "  ")
	if err != nil {
		return err
	}
	encoded = append(encoded, '\n')
	return os.WriteFile(path, encoded, 0o644)
}

func structuredSuccess(result *mcp.CallToolResult) (bool, bool) {
	document, ok := result.StructuredContent.(map[string]any)
	if !ok {
		return false, false
	}
	value, ok := document["success"].(bool)
	return value, ok
}

func run(outputDirectory string) (map[string]any, error) {
	schemaPath, err := contractSchemaPath()
	if err != nil {
		return nil, err
	}
	schemaBytes, err := os.ReadFile(schemaPath)
	if err != nil {
		return nil, fmt.Errorf("read QZX contract schema: %w", err)
	}
	var contractSchema map[string]any
	if err := json.Unmarshal(schemaBytes, &contractSchema); err != nil {
		return nil, fmt.Errorf("parse QZX contract schema: %w", err)
	}

	server := mcp.NewServer(
		&mcp.Implementation{Name: "qzx-result-contract-go-sdk-evidence", Version: "1.0.0"},
		nil,
	)
	mcp.AddTool(server, &mcp.Tool{
		Name:         toolName,
		Description:  "Look up one synthetic widget for a QZX interoperability test.",
		OutputSchema: json.RawMessage(schemaBytes),
	}, func(_ context.Context, _ *mcp.CallToolRequest, input lookupInput) (*mcp.CallToolResult, resultDocument, error) {
		if input.Fail {
			return &mcp.CallToolResult{IsError: true}, resultDocument{
				Success:   false,
				Message:   "The requested widget was not found.",
				ErrorCode: "widget_not_found",
				Details:   widgetDetails{WidgetID: "missing-widget"},
			}, nil
		}
		return &mcp.CallToolResult{}, resultDocument{
			Success: true,
			Message: "The requested widget was returned.",
			Details: widgetDetails{WidgetID: "widget-1", Status: "ready"},
		}, nil
	})

	clientTransport, serverTransport := mcp.NewInMemoryTransports()
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	serverSession, err := server.Connect(ctx, serverTransport, nil)
	if err != nil {
		return nil, fmt.Errorf("connect official MCP server: %w", err)
	}
	defer serverSession.Close()
	client := mcp.NewClient(
		&mcp.Implementation{Name: "qzx-result-contract-go-sdk-client", Version: "1.0.0"},
		nil,
	)
	clientSession, err := client.Connect(ctx, clientTransport, nil)
	if err != nil {
		return nil, fmt.Errorf("connect official MCP client: %w", err)
	}
	defer clientSession.Close()
	if got := clientSession.InitializeResult().ProtocolVersion; got != protocolVersion {
		return nil, fmt.Errorf("expected MCP %s, got %s", protocolVersion, got)
	}

	listedTools, err := clientSession.ListTools(ctx, nil)
	if err != nil {
		return nil, fmt.Errorf("list official MCP tools: %w", err)
	}
	var toolDefinition *mcp.Tool
	for _, tool := range listedTools.Tools {
		if tool.Name == toolName {
			toolDefinition = tool
			break
		}
	}
	if toolDefinition == nil {
		return nil, errors.New("the official MCP client did not discover lookup_widget")
	}
	if !reflect.DeepEqual(toolDefinition.OutputSchema, contractSchema) {
		return nil, errors.New("the official SDK changed the canonical inline output schema")
	}

	success, err := clientSession.CallTool(ctx, &mcp.CallToolParams{
		Name:      toolName,
		Arguments: map[string]any{"fail": false},
	})
	if err != nil {
		return nil, fmt.Errorf("call success case: %w", err)
	}
	failure, err := clientSession.CallTool(ctx, &mcp.CallToolParams{
		Name:      toolName,
		Arguments: map[string]any{"fail": true},
	})
	if err != nil {
		return nil, fmt.Errorf("call failure case: %w", err)
	}
	if value, ok := structuredSuccess(success); !ok || !value || success.IsError {
		return nil, errors.New("the official MCP client observed an inconsistent success result")
	}
	if value, ok := structuredSuccess(failure); !ok || value || !failure.IsError {
		return nil, errors.New("the official MCP client observed an inconsistent failure result")
	}

	absOutput, err := filepath.Abs(outputDirectory)
	if err != nil {
		return nil, fmt.Errorf("resolve output directory: %w", err)
	}
	if err := os.MkdirAll(absOutput, 0o755); err != nil {
		return nil, fmt.Errorf("create output directory: %w", err)
	}
	metadata := map[string]any{
		"evidence_kind":             "qzx_maintained_reference",
		"independent_adoption":      false,
		"protocol":                  protocolVersion,
		"protocol_era":              "legacy_initialize",
		"transport":                 "in_process_newline_delimited_json",
		"jsonrpc_framing_exercised": true,
		"wire_capture_retained":     false,
		"serialization":             "encoding_json_of_official_sdk_models",
		"packages": map[string]any{
			"github.com/modelcontextprotocol/go-sdk": moduleVersion("github.com/modelcontextprotocol/go-sdk"),
		},
		"runtime": map[string]any{
			"go":           runtime.Version(),
			"platform":     runtime.GOOS,
			"architecture": runtime.GOARCH,
		},
		"output_directory": absOutput,
		"files": []string{
			"tool-definition.json",
			"success.json",
			"failure.json",
			"evidence-metadata.json",
		},
	}
	for name, document := range map[string]any{
		"tool-definition.json":   toolDefinition,
		"success.json":           success,
		"failure.json":           failure,
		"evidence-metadata.json": metadata,
	} {
		if err := writeJSON(filepath.Join(absOutput, name), document); err != nil {
			return nil, fmt.Errorf("write %s: %w", name, err)
		}
	}
	return metadata, nil
}

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "Usage: go run . <output-directory>")
		os.Exit(2)
	}
	metadata, err := run(os.Args[1])
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	result := map[string]any{
		"success": true,
		"message": "Official MCP Go SDK v1.6.1 reference evidence generated.",
		"details": metadata,
	}
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(result); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
