use tokio::net::TcpStream;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use std::net::SocketAddr;
use tokio::time::{timeout, Duration};
use tracing::{info, error, debug};
use crate::pool::TcpPool;
use crate::tracepoint::emit_http_status_udp;

#[derive(Debug, PartialEq, Eq)]
enum ConnectionState {
    NewConnection,
    ConnectingToBackend,
    WritingRequestHeader,
    ReadingResponseHeader,
    WritingResponseHeader,
    ForwardingResponse,
    Tunneling,
    Closed,
}

const BUFFER_SIZE: usize = 8192;

// 查找 HTTP 头部结束 (\r\n\r\n)
fn find_header_end(buffer: &[u8]) -> Option<usize> {
    static HEADER_END: &[u8] = b"\r\n\r\n";
    buffer.windows(HEADER_END.len()).position(|window| window == HEADER_END)
}

// 修改请求头
fn modify_request_header(buffer: &[u8], backend_addr: SocketAddr) -> Option<(Vec<u8>, bool)> {
    let request_str = String::from_utf8_lossy(buffer);
    let mut lines = request_str.lines().peekable();
    if lines.peek().is_none() { return None; }

    let mut modified_request = String::new();
    let mut is_websocket = false;
    let backend_host_port = format!("{}", backend_addr);

    // 检查是否为 WebSocket
    if request_str.to_lowercase().contains("upgrade: websocket") && request_str.to_lowercase().contains("connection: upgrade") {
        is_websocket = true;
    }

    // 迭代并修改头部
    for line in lines {
        if line.is_empty() { break; }

        let lower_line = line.to_lowercase();

        if lower_line.starts_with("host:") {
            // 重写 Host 头部
            // Sanic 可能对 Host 头部有严格校验，直接使用后端 IP:Port
            modified_request.push_str(&format!("Host: {}:{}\r\n", backend_addr.ip(), backend_addr.port()));
        } else if lower_line.starts_with("connection:") {
            // 重写 Connection 头部
            if !is_websocket {
                modified_request.push_str("Connection: close\r\n"); // HTTP/1.1 代理使用 close
            } else {
                modified_request.push_str(&format!("{}\r\n", line)); // WebSocket 保持
            }
        } else {
            // 复制其他头部 (包括请求行)
            modified_request.push_str(&format!("{}\r\n", line));
        }
    }

    // 附加空行以结束头部
    modified_request.push_str("\r\n");

    // 复制请求体 (如果有)
    if let Some(header_end_pos) = find_header_end(buffer) {
        let body_start = header_end_pos + 4;
        let body = &buffer[body_start..];

        let mut result_vec = modified_request.into_bytes();
        result_vec.extend_from_slice(body);
        return Some((result_vec, is_websocket));
    }

    // 如果没有 body，只返回头部
    Some((modified_request.into_bytes(), is_websocket))
}

pub async fn proxy_stream(mut client_stream: TcpStream, pool: TcpPool, backend_addr: SocketAddr) {
    let client_addr = match client_stream.peer_addr() {
        Ok(addr) => format!("{}", addr),
        Err(_) => "unknown".to_string(),
    };

    let (mut client_reader, mut client_writer) = client_stream.split();

    let mut state = ConnectionState::NewConnection;
    let mut is_websocket = false;
    let mut buffer = vec![0u8; BUFFER_SIZE];
    let mut bytes_read = 0;

    // --- 1. 读取客户端请求头 ---
    loop {
        match client_reader.read(&mut buffer[bytes_read..]).await {
            Ok(0) => {
                debug!("[{}] Client closed connection during header read.", client_addr);
                return;
            }
            Ok(n) => {
                bytes_read += n;
                if let Some(header_end_pos) = find_header_end(&buffer[..bytes_read]) {

                    let _header_len = header_end_pos + 4;
                    buffer.truncate(bytes_read); // 截断到实际读取的字节数

                    // --- 2. 处理和修改请求头 ---
                    let (modified_request, is_ws) = match modify_request_header(&buffer[..bytes_read], backend_addr) {
                        Some(result) => result,
                        None => {
                            error!("[{}] Failed to process request header.", client_addr);
                            return;
                        }
                    };

                    let is_websocket = is_ws;
                    state = ConnectionState::ConnectingToBackend;
                    debug!("State changed: {:?}", state);

                    // --- 3. 从连接池获取连接并发送请求 ---
                    let timeout_duration = Duration::from_secs(5);
                    let mut backend_connection = match timeout(timeout_duration, pool.get()).await {
                        Ok(Ok(conn_obj)) => conn_obj,
                        Ok(Err(e)) => {
                            error!("[{}] Failed to get backend connection from pool: {:?}", client_addr, e);
                            let _ = client_writer.write_all(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n").await;
                            return;
                        }
                        Err(_) => { // Timeout 发生
                            error!("[{}] Failed to get backend connection from pool (timeout).", client_addr);
                            let _ = client_writer.write_all(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n").await;
                            return;
                        }
                    };

                    let (mut backend_reader, mut backend_writer) = backend_connection.split();

                    state = ConnectionState::WritingRequestHeader;

                    // 写入修改后的请求头和剩余的 body
                    if let Err(e) = backend_writer.write_all(&modified_request).await {
                        error!("[{}] Failed to write request to backend: {}", client_addr, e);
                        return;
                    }
                    state = ConnectionState::ReadingResponseHeader;

                    // --- 4. 转发逻辑 (HTTP 或 WebSocket) ---
                    if is_websocket {
                        info!("[{}] WebSocket initiated. Switching to tunnel mode.", client_addr);
                        state = ConnectionState::Tunneling;
                        debug!("State changed: {:?}", state);

                        let client_to_backend = tokio::io::copy(&mut client_reader, &mut backend_writer);
                        let backend_to_client = tokio::io::copy(&mut backend_reader, &mut client_writer);

                        tokio::select! {
                            _ = client_to_backend => {},
                            _ = backend_to_client => {},
                        }

                    } else {
                        // HTTP 代理模式：读取响应头并转发
                        let mut response_buffer = vec![0u8; BUFFER_SIZE];
                        let mut response_bytes_read = 0;

                        loop {
                            match backend_reader.read(&mut response_buffer[response_bytes_read..]).await {
                                Ok(0) => break,
                                Ok(n) => {
                                    response_bytes_read += n;
                                    if let Some(_) = find_header_end(&response_buffer[..response_bytes_read]) {
                                        break;
                                    }
                                }
                                Err(e) => {
                                    error!("[{}] Error reading response header from backend: {}", client_addr, e);
                                    return;
                                }
                            }
                            if response_bytes_read >= BUFFER_SIZE { break; }
                        }

                        if response_bytes_read > 0 {
                            // 发送响应头给客户端
                            if let Err(e) = client_writer.write_all(&response_buffer[..response_bytes_read]).await {
                                error!("[{}] Failed to write response header to client: {}", client_addr, e);
                                return;
                            } else {
                             if let Ok(header_str) = String::from_utf8(response_buffer[..response_bytes_read].to_vec()) {
                                    if let Some(code_str) = header_str.split_whitespace().nth(1) {
                                        if let Ok(code) = code_str.parse::<u16>() {
                                            emit_http_status_udp(code);
                                        }
                                    }
                                }
                            }

                            state = ConnectionState::ForwardingResponse;

                            if let Err(e) = tokio::io::copy(&mut backend_reader, &mut client_writer).await {
                                error!("[{}] Error during response body forwarding: {}", client_addr, e);
                            }
                            if let Err(e) = client_writer.shutdown().await {
                                error!("[{}] Error shutting down client writer: {}", client_addr, e);
                            }
                            break;
                        }
                    }

                    break;
                }
            }
            Err(e) => {
                error!("[{}] Error reading from client: {}", client_addr, e);
                return;
            }
        }
    }

    state = ConnectionState::Closed;
    debug!("[{}] Connection finished. Final State: {:?}", client_addr, state);
}
