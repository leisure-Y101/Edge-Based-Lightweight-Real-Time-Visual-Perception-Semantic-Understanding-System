import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';

// 默认指向云端 WebRTC 播放页（低延迟）
const String kDefaultUrl = 'http://47.238.226.101:8889/cam';
const String kPrefsKey = 'view_url';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MonitorApp());
}

class MonitorApp extends StatelessWidget {
  const MonitorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '监控',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(brightness: Brightness.dark),
      home: const WebPlayerPage(),
    );
  }
}

class WebPlayerPage extends StatefulWidget {
  const WebPlayerPage({super.key});
  @override
  State<WebPlayerPage> createState() => _WebPlayerPageState();
}

class _WebPlayerPageState extends State<WebPlayerPage> {
  WebViewController? _controller;
  String _url = kDefaultUrl;
  int _progress = 0;

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    final prefs = await SharedPreferences.getInstance();
    _url = prefs.getString(kPrefsKey) ?? kDefaultUrl;
    _load();
  }

  void _load() {
    final controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFF000000))
      ..setNavigationDelegate(NavigationDelegate(
        onProgress: (p) {
          if (mounted) setState(() => _progress = p);
        },
        onPageFinished: (_) {
          if (mounted) setState(() => _progress = 100);
        },
      ))
      ..loadRequest(Uri.parse(_url));

    final platform = controller.platform;
    if (platform is AndroidWebViewController) {
      platform.setMediaPlaybackRequiresUserGesture(false);
    }
    setState(() => _controller = controller);
  }

  Future<void> _editUrl() async {
    final te = TextEditingController(text: _url);
    final r = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('设置播放地址'),
        content: TextField(
          controller: te,
          autofocus: true,
          decoration: const InputDecoration(hintText: 'http://服务器:8889/cam'),
          keyboardType: TextInputType.url,
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(ctx, te.text.trim()),
              child: const Text('保存')),
        ],
      ),
    );
    if (r != null && r.isNotEmpty) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(kPrefsKey, r);
      _url = r;
      _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Stack(
          children: [
            if (controller != null)
              WebViewWidget(controller: controller)
            else
              const Center(child: CircularProgressIndicator()),
            if (_progress < 100)
              LinearProgressIndicator(value: _progress / 100.0),
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              child: Row(
                children: [
                  const Spacer(),
                  IconButton(
                    icon: const Icon(Icons.refresh, color: Colors.white70),
                    onPressed: _load,
                  ),
                  IconButton(
                    icon: const Icon(Icons.settings, color: Colors.white70),
                    onPressed: _editUrl,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
