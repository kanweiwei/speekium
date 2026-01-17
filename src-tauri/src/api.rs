// ============================================================================
// API Module - LLM API Testing and Connection
// ============================================================================

use reqwest;

/// Test Ollama API connection
#[tauri::command]
pub async fn test_ollama_connection(base_url: String, model: String) -> Result<serde_json::Value, String> {
    // Use reqwest to test Ollama connection directly
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    // Test 1: Check if Ollama service is running
    let tags_url = format!("{}/api/tags", base_url);
    let response = client
        .get(&tags_url)
        .send()
        .await;

    match response {
        Ok(resp) => {
            if resp.status().is_success() {
                // Test 2: Check if specified model exists
                let models = resp.json::<serde_json::Value>()
                    .await
                    .map_err(|e| format!("Failed to parse models list: {}", e))?;

                if let Some(models_array) = models.get("models").and_then(|m| m.as_array()) {
                    let model_exists = models_array.iter().any(|m| {
                        m.get("name")
                            .and_then(|n| n.as_str())
                            .map(|n| n.starts_with(&model) || n == model)
                            .unwrap_or(false)
                    });

                    if model_exists {
                        return Ok(serde_json::json!({
                            "success": true,
                            "message": format!("连接成功，模型 {} 已安装", model)
                        }));
                    } else {
                        return Ok(serde_json::json!({
                            "success": false,
                            "error": format!("模型 {} 未安装，请先运行: ollama pull {}", model, model)
                        }));
                    }
                } else {
                    return Ok(serde_json::json!({
                        "success": false,
                        "error": "无法解析模型列表"
                    }));
                }
            } else {
                return Ok(serde_json::json!({
                    "success": false,
                    "error": format!("Ollama 服务返回错误状态: {}", resp.status())
                }));
            }
        }
        Err(e) => {
            return Ok(serde_json::json!({
                "success": false,
                "error": format!("无法连接到 Ollama 服务: {}", e)
            }));
        }
    }
}

/// Get list of installed Ollama models
#[tauri::command]
pub async fn list_ollama_models(base_url: String) -> Result<Vec<String>, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let tags_url = format!("{}/api/tags", base_url);
    let response = client
        .get(&tags_url)
        .send()
        .await
        .map_err(|e| format!("Failed to connect to Ollama: {}", e))?;

    if !response.status().is_success() {
        return Err(format!("Ollama returned error status: {}", response.status()));
    }

    let data = response.json::<serde_json::Value>()
        .await
        .map_err(|e| format!("Failed to parse response: {}", e))?;

    let models = data.get("models")
        .and_then(|m| m.as_array())
        .ok_or_else(|| "No models found in response".to_string())?;

    let model_names: Vec<String> = models.iter()
        .filter_map(|m| m.get("name"))
        .filter_map(|n| n.as_str())
        .map(|s| s.to_string())
        .collect();

    for _model in &model_names {
    }

    Ok(model_names)
}

/// Test OpenAI API connection
#[tauri::command]
pub async fn test_openai_connection(api_key: String, model: String) -> Result<serde_json::Value, String> {
    if api_key.is_empty() {
        return Ok(serde_json::json!({
            "success": false,
            "error": "API Key is empty. Please enter your OpenAI API key."
        }));
    }

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let payload = serde_json::json!({
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Hi"
            }
        ],
        "max_tokens": 1
    });

    let response = client
        .post("https://api.openai.com/v1/chat/completions")
        .header("Authorization", format!("Bearer {}", api_key))
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await;

    match response {
        Ok(resp) => {
            if resp.status().is_success() {
                return Ok(serde_json::json!({
                    "success": true,
                    "message": "OpenAI API connection successful"
                }));
            } else {
                let status = resp.status();
                let error_text = resp.text().await.unwrap_or_else(|_| "Unknown error".to_string());
                return Ok(serde_json::json!({
                    "success": false,
                    "error": format!("API error: {} - {}", status, error_text)
                }));
            }
        }
        Err(e) => {
            return Ok(serde_json::json!({
                "success": false,
                "error": format!("Connection failed: {}", e)
            }));
        }
    }
}

/// Test OpenRouter API connection
#[tauri::command]
pub async fn test_openrouter_connection(api_key: String, model: String) -> Result<serde_json::Value, String> {
    if api_key.is_empty() {
        return Ok(serde_json::json!({
            "success": false,
            "error": "API Key is empty. Please enter your OpenRouter API key."
        }));
    }

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let payload = serde_json::json!({
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Hi"
            }
        ],
        "max_tokens": 1
    });

    let response = client
        .post("https://openrouter.ai/api/v1/chat/completions")
        .header("Authorization", format!("Bearer {}", api_key))
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await;

    match response {
        Ok(resp) => {
            if resp.status().is_success() {
                return Ok(serde_json::json!({
                    "success": true,
                    "message": "OpenRouter API connection successful"
                }));
            } else {
                let status = resp.status();
                let error_text = resp.text().await.unwrap_or_else(|_| "Unknown error".to_string());
                return Ok(serde_json::json!({
                    "success": false,
                    "error": format!("API error: {} - {}", status, error_text)
                }));
            }
        }
        Err(e) => {
            return Ok(serde_json::json!({
                "success": false,
                "error": format!("Connection failed: {}", e)
            }));
        }
    }
}

/// Test Custom OpenAI-compatible API connection
#[tauri::command]
pub async fn test_custom_connection(api_key: String, base_url: String, model: String) -> Result<serde_json::Value, String> {
    if base_url.is_empty() {
        return Ok(serde_json::json!({
            "success": false,
            "error": "Base URL is empty. Please enter your custom API URL."
        }));
    }

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let payload = serde_json::json!({
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Hi"
            }
        ],
        "max_tokens": 1
    });

    // Ensure base_url doesn't end with /chat/completions
    let url = if base_url.ends_with("/chat/completions") {
        base_url
    } else {
        format!("{}/chat/completions", base_url.trim_end_matches('/'))
    };

    let mut request = client
        .post(&url)
        .header("Content-Type", "application/json");

    // Only add Authorization header if api_key is provided
    if !api_key.is_empty() {
        request = request.header("Authorization", format!("Bearer {}", api_key));
    }

    let response = request
        .json(&payload)
        .send()
        .await;

    match response {
        Ok(resp) => {
            if resp.status().is_success() {
                return Ok(serde_json::json!({
                    "success": true,
                    "message": "Custom API connection successful"
                }));
            } else {
                let status = resp.status();
                let error_text = resp.text().await.unwrap_or_else(|_| "Unknown error".to_string());
                return Ok(serde_json::json!({
                    "success": false,
                    "error": format!("API error: {} - {}", status, error_text)
                }));
            }
        }
        Err(e) => {
            return Ok(serde_json::json!({
                "success": false,
                "error": format!("Connection failed: {}", e)
            }));
        }
    }
}

/// Test ZhipuAI API connection
#[tauri::command]
pub async fn test_zhipu_connection(api_key: String, base_url: String, model: String) -> Result<serde_json::Value, String> {
    if api_key.is_empty() {
        return Ok(serde_json::json!({
            "success": false,
            "error": "API Key is empty. Please enter your ZhipuAI API key."
        }));
    }

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let payload = serde_json::json!({
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Hi"
            }
        ],
        "max_tokens": 1
    });

    // Ensure base_url doesn't end with /chat/completions
    let url = if base_url.ends_with("/chat/completions") {
        base_url
    } else {
        format!("{}/chat/completions", base_url.trim_end_matches('/'))
    };

    let response = client
        .post(&url)
        .header("Content-Type", "application/json")
        .header("Authorization", format!("Bearer {}", api_key))
        .json(&payload)
        .send()
        .await;

    match response {
        Ok(resp) => {
            if resp.status().is_success() {
                return Ok(serde_json::json!({
                    "success": true,
                    "message": "ZhipuAI connection successful"
                }));
            } else {
                let status = resp.status();
                let error_text = resp.text().await.unwrap_or_else(|_| "Unknown error".to_string());
                return Ok(serde_json::json!({
                    "success": false,
                    "error": format!("API error: {} - {}", status, error_text)
                }));
            }
        }
        Err(e) => {
            return Ok(serde_json::json!({
                "success": false,
                "error": format!("Connection failed: {}", e)
            }));
        }
    }
}
