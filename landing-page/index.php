<?php
declare(strict_types=1);

const LANDING_DB_FILE = __DIR__ . '/landing.sqlite';
const LANDING_DEFAULT_ADMIN_USER = 'admin';
const LANDING_DEFAULT_ADMIN_PASSWORD = 'change-me-now';
const LANDING_LOGIN_MAX_ATTEMPTS = 8;
const LANDING_LOGIN_WINDOW_SECONDS = 900;
const LANDING_CONTACT_MAX_SUBMISSIONS = 5;
const LANDING_CONTACT_WINDOW_SECONDS = 300;

ini_set('session.use_strict_mode', '1');
ini_set('session.use_only_cookies', '1');

$secureCookie = !empty($_SERVER['HTTPS']) && strtolower((string) $_SERVER['HTTPS']) !== 'off';
session_set_cookie_params([
    'lifetime' => 0,
    'path' => '/',
    'secure' => $secureCookie,
    'httponly' => true,
    'samesite' => 'Strict',
]);

session_start();

header('X-Frame-Options: DENY');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header('Permissions-Policy: camera=(), microphone=(), geolocation=()');
header("Content-Security-Policy: default-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; object-src 'none'; connect-src 'self'; script-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com;");

function db(): PDO
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }

    $pdo = new PDO('sqlite:' . LANDING_DB_FILE);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    $pdo->exec('PRAGMA foreign_keys = ON;');
    if (is_file(LANDING_DB_FILE)) {
        @chmod(LANDING_DB_FILE, 0600);
    }
    return $pdo;
}

function init_schema(PDO $pdo): void
{
    $pdo->exec(
        "CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );"
    );

    $pdo->exec(
        "CREATE TABLE IF NOT EXISTS site_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL
        );"
    );

    $pdo->exec(
        "CREATE TABLE IF NOT EXISTS content_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 100,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );"
    );

    $pdo->exec(
        "CREATE TABLE IF NOT EXISTS content_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            badge TEXT NOT NULL DEFAULT '',
            cta_label TEXT NOT NULL DEFAULT '',
            cta_url TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 100,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(category_id) REFERENCES content_categories(id) ON DELETE CASCADE
        );"
    );

    $pdo->exec(
        "CREATE TABLE IF NOT EXISTS contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            subject TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );"
    );

    $pdo->exec(
        "CREATE TABLE IF NOT EXISTS request_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_key TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );"
    );
    $pdo->exec("CREATE INDEX IF NOT EXISTS idx_request_log_action_ip_time ON request_log(action_key, ip_address, created_at);");
}

function seed_defaults(PDO $pdo): void
{
    $defaultSettings = [
        'site_title' => "myBay",
        'site_kicker' => 'Snap. List. Sell.',
        'hero_heading' => 'eBay listings in under 60 seconds.',
        'hero_subheading' => 'From iPhone photos to live listing in one flow. Built for busy sellers who want speed without losing quality.',
        'mac_download_url' => '../dist/MyBay-1.0.0.dmg',
        'windows_download_url' => '',
        'linux_download_url' => '',
        'contact_email' => 'support@example.com',
        'footer_note' => 'Built for real sellers. Focused on speed, reliability, and clean listings.',
    ];

    $insertSetting = $pdo->prepare(
        'INSERT OR IGNORE INTO site_settings (setting_key, setting_value) VALUES (:key, :value)'
    );
    foreach ($defaultSettings as $key => $value) {
        $insertSetting->execute([':key' => $key, ':value' => $value]);
    }

    $categoryCount = (int) $pdo->query('SELECT COUNT(*) FROM content_categories')->fetchColumn();
    if ($categoryCount === 0) {
        $insertCategory = $pdo->prepare(
            'INSERT INTO content_categories (name, slug, description, sort_order, is_active) VALUES (:name, :slug, :description, :sort_order, 1)'
        );

        $insertCategory->execute([
            ':name' => 'Why Sellers Use It',
            ':slug' => 'why-sellers-use-it',
            ':description' => 'Operational wins that matter when listing every day.',
            ':sort_order' => 10,
        ]);
        $insertCategory->execute([
            ':name' => 'Built For Speed',
            ':slug' => 'built-for-speed',
            ':description' => 'Design and workflow choices focused on getting listings live fast.',
            ':sort_order' => 20,
        ]);
        $insertCategory->execute([
            ':name' => 'Roadmap',
            ':slug' => 'roadmap',
            ':description' => 'What is shipping next.',
            ':sort_order' => 30,
        ]);
    }

    $itemCount = (int) $pdo->query('SELECT COUNT(*) FROM content_items')->fetchColumn();
    if ($itemCount === 0) {
        $categories = [];
        foreach ($pdo->query('SELECT id, slug FROM content_categories') as $row) {
            $categories[(string) $row['slug']] = (int) $row['id'];
        }

        $insertItem = $pdo->prepare(
            'INSERT INTO content_items (category_id, title, summary, content, badge, cta_label, cta_url, sort_order, is_active) 
             VALUES (:category_id, :title, :summary, :content, :badge, :cta_label, :cta_url, :sort_order, 1)'
        );

        $insertItem->execute([
            ':category_id' => $categories['why-sellers-use-it'] ?? 1,
            ':title' => 'One-Click Publish Flow',
            ':summary' => 'From draft to listing in one action.',
            ':content' => 'The app handles inventory item creation, offer creation, and publish calls end-to-end, with clear status feedback.',
            ':badge' => 'Core',
            ':cta_label' => '',
            ':cta_url' => '',
            ':sort_order' => 10,
        ]);

        $insertItem->execute([
            ':category_id' => $categories['built-for-speed'] ?? 2,
            ':title' => 'Phone Photo Intake',
            ':summary' => 'Snap on phone, list on desktop.',
            ':content' => 'QR-driven capture keeps image intake fast and simple, so listing throughput stays high during sourcing sessions.',
            ':badge' => 'Workflow',
            ':cta_label' => '',
            ':cta_url' => '',
            ':sort_order' => 10,
        ]);

        $insertItem->execute([
            ':category_id' => $categories['roadmap'] ?? 3,
            ':title' => 'Windows + Linux Packaging',
            ':summary' => 'Planned platform expansion.',
            ':content' => 'Cross-platform support is possible with targeted QA, signing, and installer work per operating system.',
            ':badge' => 'Planned',
            ':cta_label' => '',
            ':cta_url' => '',
            ':sort_order' => 10,
        ]);
    }
}

function ensure_admin_user(PDO $pdo): void
{
    $count = (int) $pdo->query('SELECT COUNT(*) FROM admin_users')->fetchColumn();
    if ($count > 0) {
        return;
    }

    $seedPassword = trim((string) getenv('LANDING_ADMIN_PASSWORD'));
    if ($seedPassword === '') {
        $seedPassword = LANDING_DEFAULT_ADMIN_PASSWORD;
    }

    $hash = password_hash($seedPassword, PASSWORD_DEFAULT);
    $stmt = $pdo->prepare('INSERT INTO admin_users (username, password_hash) VALUES (:username, :password_hash)');
    $stmt->execute([
        ':username' => LANDING_DEFAULT_ADMIN_USER,
        ':password_hash' => $hash,
    ]);
}

function e(?string $value): string
{
    return htmlspecialchars((string) $value, ENT_QUOTES, 'UTF-8');
}

function redirect(string $url): void
{
    header('Location: ' . $url);
    exit;
}

function set_flash(string $type, string $message): void
{
    $_SESSION['landing_flash'] = [
        'type' => $type,
        'message' => $message,
    ];
}

function pull_flash(): ?array
{
    $flash = $_SESSION['landing_flash'] ?? null;
    unset($_SESSION['landing_flash']);
    return is_array($flash) ? $flash : null;
}

function csrf_token(): string
{
    if (empty($_SESSION['landing_csrf'])) {
        $_SESSION['landing_csrf'] = bin2hex(random_bytes(24));
    }
    return (string) $_SESSION['landing_csrf'];
}

function verify_csrf_token(?string $token): bool
{
    $expected = (string) ($_SESSION['landing_csrf'] ?? '');
    if ($expected === '' || $token === null) {
        return false;
    }
    return hash_equals($expected, $token);
}

function is_admin_authenticated(): bool
{
    return !empty($_SESSION['landing_admin_user_id']);
}

function slugify(string $value): string
{
    $value = strtolower(trim($value));
    $value = preg_replace('/[^a-z0-9]+/', '-', $value) ?? '';
    $value = trim($value, '-');
    return $value === '' ? 'category-' . random_int(1000, 9999) : $value;
}

function load_settings(PDO $pdo): array
{
    $settings = [];
    foreach ($pdo->query('SELECT setting_key, setting_value FROM site_settings') as $row) {
        $settings[(string) $row['setting_key']] = (string) $row['setting_value'];
    }
    return $settings;
}

function get_setting(array $settings, string $key, string $default = ''): string
{
    return array_key_exists($key, $settings) ? (string) $settings[$key] : $default;
}

function save_setting(PDO $pdo, string $key, string $value): void
{
    $stmt = $pdo->prepare(
        'INSERT INTO site_settings (setting_key, setting_value) VALUES (:key, :value)
         ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value'
    );
    $stmt->execute([
        ':key' => $key,
        ':value' => $value,
    ]);
}

function fetch_categories(PDO $pdo, bool $includeInactive = false): array
{
    $sql = 'SELECT id, name, slug, description, sort_order, is_active, created_at, updated_at FROM content_categories';
    if (!$includeInactive) {
        $sql .= ' WHERE is_active = 1';
    }
    $sql .= ' ORDER BY sort_order ASC, name ASC';
    return $pdo->query($sql)->fetchAll();
}

function fetch_items(PDO $pdo, bool $includeInactive = false): array
{
    $sql = "
        SELECT i.id, i.category_id, i.title, i.summary, i.content, i.badge, i.cta_label, i.cta_url, i.sort_order, i.is_active, i.created_at, i.updated_at,
               c.name AS category_name, c.slug AS category_slug
        FROM content_items i
        INNER JOIN content_categories c ON c.id = i.category_id
    ";
    if (!$includeInactive) {
        $sql .= ' WHERE i.is_active = 1 AND c.is_active = 1';
    }
    $sql .= ' ORDER BY c.sort_order ASC, i.sort_order ASC, i.title ASC';
    return $pdo->query($sql)->fetchAll();
}

function group_items_by_category(array $items): array
{
    $grouped = [];
    foreach ($items as $item) {
        $categoryId = (int) $item['category_id'];
        if (!isset($grouped[$categoryId])) {
            $grouped[$categoryId] = [];
        }
        $grouped[$categoryId][] = $item;
    }
    return $grouped;
}

function fetch_messages(PDO $pdo): array
{
    return $pdo->query(
        'SELECT id, name, email, subject, message, is_read, created_at 
         FROM contact_messages
         ORDER BY is_read ASC, created_at DESC'
    )->fetchAll();
}

function get_admin_user(PDO $pdo, string $username): ?array
{
    $stmt = $pdo->prepare('SELECT id, username, password_hash FROM admin_users WHERE username = :username LIMIT 1');
    $stmt->execute([':username' => $username]);
    $row = $stmt->fetch();
    return $row ?: null;
}

function client_ip_address(): string
{
    $forwarded = (string) ($_SERVER['HTTP_X_FORWARDED_FOR'] ?? '');
    if ($forwarded !== '') {
        $parts = explode(',', $forwarded);
        $candidate = trim((string) $parts[0]);
        if (filter_var($candidate, FILTER_VALIDATE_IP)) {
            return $candidate;
        }
    }

    $remoteAddr = trim((string) ($_SERVER['REMOTE_ADDR'] ?? ''));
    if (filter_var($remoteAddr, FILTER_VALIDATE_IP)) {
        return $remoteAddr;
    }
    return '0.0.0.0';
}

function is_local_request(): bool
{
    $ip = client_ip_address();
    return $ip === '127.0.0.1' || $ip === '::1';
}

function prune_request_log(PDO $pdo, int $oldestTimestamp): void
{
    $stmt = $pdo->prepare('DELETE FROM request_log WHERE created_at < :oldest');
    $stmt->execute([':oldest' => $oldestTimestamp]);
}

function count_recent_requests(PDO $pdo, string $actionKey, string $ipAddress, int $windowSeconds): int
{
    $threshold = time() - $windowSeconds;
    $stmt = $pdo->prepare(
        'SELECT COUNT(*) FROM request_log WHERE action_key = :action_key AND ip_address = :ip_address AND created_at >= :threshold'
    );
    $stmt->execute([
        ':action_key' => $actionKey,
        ':ip_address' => $ipAddress,
        ':threshold' => $threshold,
    ]);
    return (int) $stmt->fetchColumn();
}

function register_request_attempt(PDO $pdo, string $actionKey, string $ipAddress): void
{
    $stmt = $pdo->prepare(
        'INSERT INTO request_log (action_key, ip_address, created_at) VALUES (:action_key, :ip_address, :created_at)'
    );
    $stmt->execute([
        ':action_key' => $actionKey,
        ':ip_address' => $ipAddress,
        ':created_at' => time(),
    ]);
}

function clear_request_attempts(PDO $pdo, string $actionKey, string $ipAddress): void
{
    $stmt = $pdo->prepare('DELETE FROM request_log WHERE action_key = :action_key AND ip_address = :ip_address');
    $stmt->execute([
        ':action_key' => $actionKey,
        ':ip_address' => $ipAddress,
    ]);
}

function sanitize_url(string $value, bool $allowRelative = true): string
{
    $value = trim($value);
    if ($value === '') {
        return '';
    }

    if (preg_match('/[\x00-\x1F\x7F]/', $value) === 1) {
        return '';
    }

    if ($allowRelative && preg_match('/^[a-z][a-z0-9+.-]*:/i', $value) !== 1) {
        if (str_starts_with($value, '//') || str_contains($value, '\\')) {
            return '';
        }
        return $value;
    }

    $parsed = parse_url($value);
    if ($parsed === false || empty($parsed['scheme']) || empty($parsed['host'])) {
        return '';
    }

    $scheme = strtolower((string) $parsed['scheme']);
    if (!in_array($scheme, ['http', 'https'], true)) {
        return '';
    }

    $sanitized = filter_var($value, FILTER_SANITIZE_URL);
    return is_string($sanitized) ? trim($sanitized) : '';
}

function is_strong_password(string $value): bool
{
    if (strlen($value) < 12) {
        return false;
    }
    return preg_match('/[A-Z]/', $value) === 1
        && preg_match('/[a-z]/', $value) === 1
        && preg_match('/\d/', $value) === 1;
}

$pdo = db();
init_schema($pdo);
seed_defaults($pdo);
ensure_admin_user($pdo);
prune_request_log($pdo, time() - 86400);

$isAdminView = isset($_GET['admin']) && $_GET['admin'] === '1';

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
    $action = (string) ($_POST['action'] ?? '');

    if (!verify_csrf_token($_POST['csrf_token'] ?? null)) {
        set_flash('error', 'Security token mismatch. Please try again.');
        redirect($isAdminView ? '?admin=1' : './');
    }

    if ($action === 'contact_submit') {
        $ipAddress = client_ip_address();
        $recentSubmissions = count_recent_requests($pdo, 'contact_submit', $ipAddress, LANDING_CONTACT_WINDOW_SECONDS);
        if ($recentSubmissions >= LANDING_CONTACT_MAX_SUBMISSIONS) {
            set_flash('error', 'Too many messages in a short time. Please wait a few minutes and try again.');
            redirect('./#contact');
        }

        $name = trim((string) ($_POST['name'] ?? ''));
        $email = trim((string) ($_POST['email'] ?? ''));
        $subject = trim((string) ($_POST['subject'] ?? ''));
        $message = trim((string) ($_POST['message'] ?? ''));

        if ($name === '' || $email === '' || $message === '') {
            set_flash('error', 'Name, email, and message are required.');
            redirect('./#contact');
        }

        if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
            set_flash('error', 'Please enter a valid email address.');
            redirect('./#contact');
        }

        $stmt = $pdo->prepare(
            'INSERT INTO contact_messages (name, email, subject, message, is_read) VALUES (:name, :email, :subject, :message, 0)'
        );
        $stmt->execute([
            ':name' => mb_substr($name, 0, 120),
            ':email' => mb_substr($email, 0, 160),
            ':subject' => mb_substr($subject, 0, 200),
            ':message' => mb_substr($message, 0, 5000),
        ]);
        register_request_attempt($pdo, 'contact_submit', $ipAddress);

        set_flash('success', 'Thanks. Your message was sent.');
        redirect('./#contact');
    }

    if ($action === 'admin_login') {
        $ipAddress = client_ip_address();
        $failedAttempts = count_recent_requests($pdo, 'admin_login_failed', $ipAddress, LANDING_LOGIN_WINDOW_SECONDS);
        if ($failedAttempts >= LANDING_LOGIN_MAX_ATTEMPTS) {
            set_flash('error', 'Too many failed login attempts. Please wait 15 minutes and try again.');
            redirect('?admin=1');
        }

        $username = trim((string) ($_POST['username'] ?? ''));
        $password = (string) ($_POST['password'] ?? '');

        $admin = get_admin_user($pdo, $username);
        if (
            $admin
            && password_verify(LANDING_DEFAULT_ADMIN_PASSWORD, (string) $admin['password_hash'])
            && !is_local_request()
        ) {
            register_request_attempt($pdo, 'admin_login_failed', $ipAddress);
            set_flash('error', 'Default admin password is blocked for non-local access. Set LANDING_ADMIN_PASSWORD and rotate credentials.');
            redirect('?admin=1');
        }

        if ($admin && password_verify($password, (string) $admin['password_hash'])) {
            session_regenerate_id(true);
            $_SESSION['landing_admin_user_id'] = (int) $admin['id'];
            $_SESSION['landing_admin_username'] = (string) $admin['username'];
            clear_request_attempts($pdo, 'admin_login_failed', $ipAddress);
            set_flash('success', 'Logged in.');
            redirect('?admin=1');
        }

        register_request_attempt($pdo, 'admin_login_failed', $ipAddress);
        set_flash('error', 'Invalid admin credentials.');
        redirect('?admin=1');
    }

    if (!is_admin_authenticated()) {
        set_flash('error', 'You must be signed in.');
        redirect('?admin=1');
    }

    if ($action === 'admin_logout') {
        session_regenerate_id(true);
        unset($_SESSION['landing_admin_user_id'], $_SESSION['landing_admin_username']);
        set_flash('success', 'Logged out.');
        redirect('?admin=1');
    }

    switch ($action) {
        case 'save_settings':
            $plainKeys = [
                'site_title',
                'site_kicker',
                'hero_heading',
                'hero_subheading',
                'contact_email',
                'footer_note',
            ];
            $urlKeys = [
                'mac_download_url',
                'windows_download_url',
                'linux_download_url',
            ];

            $contactEmail = trim((string) ($_POST['contact_email'] ?? ''));
            if ($contactEmail !== '' && !filter_var($contactEmail, FILTER_VALIDATE_EMAIL)) {
                set_flash('error', 'Contact email is invalid.');
                redirect('?admin=1#settings');
            }

            foreach ($plainKeys as $key) {
                save_setting($pdo, $key, trim((string) ($_POST[$key] ?? '')));
            }

            foreach ($urlKeys as $key) {
                $rawValue = trim((string) ($_POST[$key] ?? ''));
                $safeUrl = sanitize_url($rawValue, true);
                if ($rawValue !== '' && $safeUrl === '') {
                    set_flash('error', 'One or more download URLs are invalid. Use https:// or a relative path.');
                    redirect('?admin=1#settings');
                }
                save_setting($pdo, $key, $safeUrl);
            }
            set_flash('success', 'Site settings saved.');
            redirect('?admin=1#settings');

        case 'add_category':
            $name = trim((string) ($_POST['name'] ?? ''));
            $slugInput = trim((string) ($_POST['slug'] ?? ''));
            $description = trim((string) ($_POST['description'] ?? ''));
            $sortOrder = (int) ($_POST['sort_order'] ?? 100);
            $isActive = !empty($_POST['is_active']) ? 1 : 0;

            if ($name === '') {
                set_flash('error', 'Category name is required.');
                redirect('?admin=1#categories');
            }

            $slug = slugify($slugInput !== '' ? $slugInput : $name);

            try {
                $stmt = $pdo->prepare(
                    'INSERT INTO content_categories (name, slug, description, sort_order, is_active, updated_at)
                     VALUES (:name, :slug, :description, :sort_order, :is_active, datetime(\'now\'))'
                );
                $stmt->execute([
                    ':name' => mb_substr($name, 0, 120),
                    ':slug' => mb_substr($slug, 0, 160),
                    ':description' => mb_substr($description, 0, 500),
                    ':sort_order' => $sortOrder,
                    ':is_active' => $isActive,
                ]);
                set_flash('success', 'Category added.');
            } catch (Throwable $e) {
                set_flash('error', 'Could not add category (slug might already exist).');
            }
            redirect('?admin=1#categories');

        case 'update_category':
            $id = (int) ($_POST['id'] ?? 0);
            $name = trim((string) ($_POST['name'] ?? ''));
            $slugInput = trim((string) ($_POST['slug'] ?? ''));
            $description = trim((string) ($_POST['description'] ?? ''));
            $sortOrder = (int) ($_POST['sort_order'] ?? 100);
            $isActive = !empty($_POST['is_active']) ? 1 : 0;

            if ($id <= 0 || $name === '') {
                set_flash('error', 'Invalid category update request.');
                redirect('?admin=1#categories');
            }

            $slug = slugify($slugInput !== '' ? $slugInput : $name);
            try {
                $stmt = $pdo->prepare(
                    'UPDATE content_categories
                     SET name = :name, slug = :slug, description = :description, sort_order = :sort_order, is_active = :is_active, updated_at = datetime(\'now\')
                     WHERE id = :id'
                );
                $stmt->execute([
                    ':id' => $id,
                    ':name' => mb_substr($name, 0, 120),
                    ':slug' => mb_substr($slug, 0, 160),
                    ':description' => mb_substr($description, 0, 500),
                    ':sort_order' => $sortOrder,
                    ':is_active' => $isActive,
                ]);
                set_flash('success', 'Category updated.');
            } catch (Throwable $e) {
                set_flash('error', 'Could not update category (slug might already exist).');
            }
            redirect('?admin=1#categories');

        case 'delete_category':
            $id = (int) ($_POST['id'] ?? 0);
            if ($id > 0) {
                $stmt = $pdo->prepare('DELETE FROM content_categories WHERE id = :id');
                $stmt->execute([':id' => $id]);
                set_flash('success', 'Category deleted.');
            }
            redirect('?admin=1#categories');

        case 'add_item':
            $categoryId = (int) ($_POST['category_id'] ?? 0);
            $title = trim((string) ($_POST['title'] ?? ''));
            $summary = trim((string) ($_POST['summary'] ?? ''));
            $content = trim((string) ($_POST['content'] ?? ''));
            $badge = trim((string) ($_POST['badge'] ?? ''));
            $ctaLabel = trim((string) ($_POST['cta_label'] ?? ''));
            $ctaUrlRaw = trim((string) ($_POST['cta_url'] ?? ''));
            $ctaUrl = sanitize_url($ctaUrlRaw, true);
            $sortOrder = (int) ($_POST['sort_order'] ?? 100);
            $isActive = !empty($_POST['is_active']) ? 1 : 0;

            if ($categoryId <= 0 || $title === '') {
                set_flash('error', 'Item requires category + title.');
                redirect('?admin=1#items');
            }
            if ($ctaUrlRaw !== '' && $ctaUrl === '') {
                set_flash('error', 'CTA URL is invalid. Use https:// or a relative path.');
                redirect('?admin=1#items');
            }
            if (($ctaLabel === '') !== ($ctaUrl === '')) {
                set_flash('error', 'CTA label and CTA URL must be provided together.');
                redirect('?admin=1#items');
            }

            $stmt = $pdo->prepare(
                'INSERT INTO content_items
                 (category_id, title, summary, content, badge, cta_label, cta_url, sort_order, is_active, updated_at)
                 VALUES
                 (:category_id, :title, :summary, :content, :badge, :cta_label, :cta_url, :sort_order, :is_active, datetime(\'now\'))'
            );
            $stmt->execute([
                ':category_id' => $categoryId,
                ':title' => mb_substr($title, 0, 180),
                ':summary' => mb_substr($summary, 0, 220),
                ':content' => mb_substr($content, 0, 3000),
                ':badge' => mb_substr($badge, 0, 50),
                ':cta_label' => mb_substr($ctaLabel, 0, 60),
                ':cta_url' => mb_substr($ctaUrl, 0, 500),
                ':sort_order' => $sortOrder,
                ':is_active' => $isActive,
            ]);
            set_flash('success', 'Content block added.');
            redirect('?admin=1#items');

        case 'update_item':
            $id = (int) ($_POST['id'] ?? 0);
            $categoryId = (int) ($_POST['category_id'] ?? 0);
            $title = trim((string) ($_POST['title'] ?? ''));
            $summary = trim((string) ($_POST['summary'] ?? ''));
            $content = trim((string) ($_POST['content'] ?? ''));
            $badge = trim((string) ($_POST['badge'] ?? ''));
            $ctaLabel = trim((string) ($_POST['cta_label'] ?? ''));
            $ctaUrlRaw = trim((string) ($_POST['cta_url'] ?? ''));
            $ctaUrl = sanitize_url($ctaUrlRaw, true);
            $sortOrder = (int) ($_POST['sort_order'] ?? 100);
            $isActive = !empty($_POST['is_active']) ? 1 : 0;

            if ($id <= 0 || $categoryId <= 0 || $title === '') {
                set_flash('error', 'Invalid item update request.');
                redirect('?admin=1#items');
            }
            if ($ctaUrlRaw !== '' && $ctaUrl === '') {
                set_flash('error', 'CTA URL is invalid. Use https:// or a relative path.');
                redirect('?admin=1#items');
            }
            if (($ctaLabel === '') !== ($ctaUrl === '')) {
                set_flash('error', 'CTA label and CTA URL must be provided together.');
                redirect('?admin=1#items');
            }

            $stmt = $pdo->prepare(
                'UPDATE content_items
                 SET category_id = :category_id, title = :title, summary = :summary, content = :content, badge = :badge,
                     cta_label = :cta_label, cta_url = :cta_url, sort_order = :sort_order, is_active = :is_active, updated_at = datetime(\'now\')
                 WHERE id = :id'
            );
            $stmt->execute([
                ':id' => $id,
                ':category_id' => $categoryId,
                ':title' => mb_substr($title, 0, 180),
                ':summary' => mb_substr($summary, 0, 220),
                ':content' => mb_substr($content, 0, 3000),
                ':badge' => mb_substr($badge, 0, 50),
                ':cta_label' => mb_substr($ctaLabel, 0, 60),
                ':cta_url' => mb_substr($ctaUrl, 0, 500),
                ':sort_order' => $sortOrder,
                ':is_active' => $isActive,
            ]);
            set_flash('success', 'Content block updated.');
            redirect('?admin=1#items');

        case 'delete_item':
            $id = (int) ($_POST['id'] ?? 0);
            if ($id > 0) {
                $stmt = $pdo->prepare('DELETE FROM content_items WHERE id = :id');
                $stmt->execute([':id' => $id]);
                set_flash('success', 'Content block deleted.');
            }
            redirect('?admin=1#items');

        case 'mark_message_read':
            $id = (int) ($_POST['id'] ?? 0);
            if ($id > 0) {
                $stmt = $pdo->prepare('UPDATE contact_messages SET is_read = 1 WHERE id = :id');
                $stmt->execute([':id' => $id]);
            }
            redirect('?admin=1#messages');

        case 'mark_message_unread':
            $id = (int) ($_POST['id'] ?? 0);
            if ($id > 0) {
                $stmt = $pdo->prepare('UPDATE contact_messages SET is_read = 0 WHERE id = :id');
                $stmt->execute([':id' => $id]);
            }
            redirect('?admin=1#messages');

        case 'delete_message':
            $id = (int) ($_POST['id'] ?? 0);
            if ($id > 0) {
                $stmt = $pdo->prepare('DELETE FROM contact_messages WHERE id = :id');
                $stmt->execute([':id' => $id]);
            }
            redirect('?admin=1#messages');

        case 'change_password':
            $username = (string) ($_SESSION['landing_admin_username'] ?? '');
            $currentPassword = (string) ($_POST['current_password'] ?? '');
            $newPassword = (string) ($_POST['new_password'] ?? '');
            $confirmPassword = (string) ($_POST['confirm_password'] ?? '');

            if (!is_strong_password($newPassword)) {
                set_flash('error', 'New password must be at least 12 chars and include uppercase, lowercase, and a number.');
                redirect('?admin=1#security');
            }

            if ($newPassword !== $confirmPassword) {
                set_flash('error', 'New password and confirm password do not match.');
                redirect('?admin=1#security');
            }

            $admin = get_admin_user($pdo, $username);
            if (!$admin || !password_verify($currentPassword, (string) $admin['password_hash'])) {
                set_flash('error', 'Current password is incorrect.');
                redirect('?admin=1#security');
            }

            $stmt = $pdo->prepare('UPDATE admin_users SET password_hash = :password_hash WHERE id = :id');
            $stmt->execute([
                ':id' => (int) $admin['id'],
                ':password_hash' => password_hash($newPassword, PASSWORD_DEFAULT),
            ]);
            session_regenerate_id(true);
            set_flash('success', 'Admin password updated.');
            redirect('?admin=1#security');

        default:
            set_flash('error', 'Unsupported action.');
            redirect($isAdminView ? '?admin=1' : './');
    }
}

$flash = pull_flash();
$settings = load_settings($pdo);
$publicCategories = fetch_categories($pdo, false);
$publicItems = fetch_items($pdo, false);
$publicItemsByCategory = group_items_by_category($publicItems);

$isAdminAuthenticated = is_admin_authenticated();
$adminCategories = [];
$adminItems = [];
$adminMessages = [];
$usingDefaultPassword = false;

if ($isAdminView && $isAdminAuthenticated) {
    $adminCategories = fetch_categories($pdo, true);
    $adminItems = fetch_items($pdo, true);
    $adminMessages = fetch_messages($pdo);

    $username = (string) ($_SESSION['landing_admin_username'] ?? LANDING_DEFAULT_ADMIN_USER);
    $admin = get_admin_user($pdo, $username);
    if ($admin) {
        $usingDefaultPassword = password_verify(LANDING_DEFAULT_ADMIN_PASSWORD, (string) $admin['password_hash']);
    }
}

$csrf = csrf_token();
?>
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= e(get_setting($settings, 'site_title', "myBay")) ?> — Snap. List. Sell.</title>
    <meta name="description" content="Turn iPhone photos into eBay listings in under 60 seconds. AI-powered product analysis, one-click publishing, and a full business backend for eBay sellers.">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #09090b;
            --bg-raised: #18181b;
            --bg-card: #1c1c22;
            --bg-card-hover: #232329;
            --border: #27272a;
            --border-light: #3f3f46;
            --text: #fafafa;
            --text-secondary: #a1a1aa;
            --text-muted: #71717a;
            --accent: #3b82f6;
            --accent-hover: #60a5fa;
            --accent-glow: rgba(59, 130, 246, 0.15);
            --green: #22c55e;
            --green-glow: rgba(34, 197, 94, 0.15);
            --orange: #f97316;
            --orange-glow: rgba(249, 115, 22, 0.15);
            --purple: #a855f7;
            --purple-glow: rgba(168, 85, 247, 0.15);
            --red: #ef4444;
            --yellow: #eab308;
            --radius: 16px;
            --radius-sm: 10px;
            --radius-xs: 6px;
            --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
            --shadow-md: 0 4px 12px rgba(0,0,0,0.4);
            --shadow-lg: 0 20px 40px rgba(0,0,0,0.5);
            --shadow-glow: 0 0 60px rgba(59,130,246,0.08);

            /* admin vars */
            --admin-bg: #f5f7fb;
            --admin-card: #ffffff;
            --admin-text: #1b2333;
            --admin-line: #d6dde8;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        html { scroll-behavior: smooth; }

        body.site-mode {
            font-family: "Inter", -apple-system, BlinkMacSystemFont, sans-serif;
            color: var(--text);
            background: var(--bg);
            min-height: 100vh;
            -webkit-font-smoothing: antialiased;
            overflow-x: hidden;
        }

        /* ── Hero background ── */
        .hero-bg {
            position: relative;
            overflow: hidden;
        }
        .hero-bg::before {
            content: "";
            position: absolute;
            top: -40%; left: -20%;
            width: 140%; height: 180%;
            background:
                radial-gradient(ellipse 800px 600px at 20% 10%, rgba(59,130,246,0.18), transparent 60%),
                radial-gradient(ellipse 600px 500px at 80% 20%, rgba(168,85,247,0.12), transparent 55%),
                radial-gradient(ellipse 500px 400px at 50% 60%, rgba(34,197,94,0.06), transparent 50%);
            pointer-events: none;
            z-index: 0;
        }
        .hero-bg::after {
            content: "";
            position: absolute;
            inset: 0;
            background-image:
                linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
            background-size: 60px 60px;
            mask-image: radial-gradient(ellipse at center top, black 20%, transparent 70%);
            pointer-events: none;
            z-index: 0;
        }

        .container {
            width: 100%;
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 24px;
            position: relative;
            z-index: 1;
        }

        /* ── Navigation ── */
        .site-nav {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 0;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }
        .nav-brand {
            display: flex;
            align-items: center;
            gap: 10px;
            text-decoration: none;
            color: var(--text);
        }
        .nav-logo {
            width: 32px; height: 32px;
            border-radius: 8px;
            background: linear-gradient(135deg, var(--accent), var(--purple));
            display: flex; align-items: center; justify-content: center;
            font-weight: 800; font-size: 14px; color: #fff;
            box-shadow: 0 0 20px rgba(59,130,246,0.3);
        }
        .nav-wordmark {
            font-weight: 700;
            font-size: 1.1rem;
            letter-spacing: -0.02em;
        }
        .nav-links {
            display: flex;
            align-items: center;
            gap: 8px;
            list-style: none;
        }
        .nav-links a {
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 0.875rem;
            font-weight: 500;
            padding: 8px 14px;
            border-radius: 8px;
            transition: color 0.15s, background 0.15s;
        }
        .nav-links a:hover {
            color: var(--text);
            background: rgba(255,255,255,0.05);
        }
        .nav-links .nav-cta {
            background: var(--accent);
            color: #fff;
            font-weight: 600;
        }
        .nav-links .nav-cta:hover {
            background: var(--accent-hover);
        }

        /* ── Hero ── */
        .hero {
            padding: 80px 0 60px;
            text-align: center;
        }
        .hero-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 16px;
            border: 1px solid var(--border);
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 500;
            color: var(--text-secondary);
            background: var(--bg-raised);
            margin-bottom: 28px;
        }
        .hero-badge .dot {
            width: 6px; height: 6px;
            border-radius: 50%;
            background: var(--green);
            box-shadow: 0 0 8px var(--green);
        }
        .hero h1 {
            font-size: clamp(2.5rem, 6vw, 4.2rem);
            font-weight: 800;
            line-height: 1.08;
            letter-spacing: -0.03em;
            margin-bottom: 20px;
            background: linear-gradient(135deg, #fff 0%, #d4d4d8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .hero h1 span {
            background: linear-gradient(135deg, var(--accent), var(--purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .hero-sub {
            font-size: 1.15rem;
            color: var(--text-secondary);
            max-width: 620px;
            margin: 0 auto 36px;
            line-height: 1.7;
        }
        .hero-actions {
            display: flex;
            justify-content: center;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 16px;
        }
        .btn-primary, .btn-secondary {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 14px 28px;
            border-radius: 12px;
            font-size: 0.95rem;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s;
            border: none;
            cursor: pointer;
        }
        .btn-primary {
            background: var(--accent);
            color: #fff;
            box-shadow: 0 0 24px rgba(59,130,246,0.25);
        }
        .btn-primary:hover {
            background: var(--accent-hover);
            transform: translateY(-1px);
            box-shadow: 0 0 32px rgba(59,130,246,0.35);
        }
        .btn-secondary {
            background: var(--bg-raised);
            color: var(--text);
            border: 1px solid var(--border);
        }
        .btn-secondary:hover {
            background: var(--bg-card);
            border-color: var(--border-light);
        }
        .hero-note {
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 8px;
        }

        /* ── App Mockup ── */
        .mockup-container {
            max-width: 960px;
            margin: 48px auto 0;
            perspective: 1200px;
        }
        .app-window {
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border);
            background: #111114;
            box-shadow: var(--shadow-lg), var(--shadow-glow);
        }
        .window-bar {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 14px 18px;
            background: #0c0c0f;
            border-bottom: 1px solid var(--border);
        }
        .window-dot { width: 12px; height: 12px; border-radius: 50%; }
        .window-dot.r { background: #ff5f57; }
        .window-dot.y { background: #febc2e; }
        .window-dot.g { background: #28c840; }
        .window-title {
            flex: 1;
            text-align: center;
            font-size: 0.8rem;
            color: var(--text-muted);
            font-weight: 500;
            margin-right: 56px;
        }
        .window-body {
            display: grid;
            grid-template-columns: 200px 1fr;
            min-height: 380px;
        }
        .mock-sidebar {
            background: #0e0e12;
            border-right: 1px solid var(--border);
            padding: 16px 12px;
        }
        .mock-sidebar-title {
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--text-muted);
            margin-bottom: 12px;
        }
        .mock-draft {
            padding: 10px;
            border-radius: 8px;
            border: 1px solid var(--border);
            margin-bottom: 8px;
            background: rgba(255,255,255,0.02);
            cursor: default;
        }
        .mock-draft.active {
            border-color: var(--accent);
            background: var(--accent-glow);
        }
        .mock-draft-title {
            font-size: 0.78rem;
            font-weight: 600;
            color: var(--text);
            margin-bottom: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .mock-draft-price {
            font-size: 0.85rem;
            font-weight: 700;
            color: var(--green);
            margin-bottom: 4px;
        }
        .mock-confidence {
            height: 4px;
            border-radius: 2px;
            background: var(--border);
            overflow: hidden;
        }
        .mock-confidence-fill {
            height: 100%;
            border-radius: 2px;
            background: linear-gradient(90deg, var(--accent), var(--green));
        }
        .mock-main {
            padding: 24px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
        }
        .mock-images {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .mock-img-placeholder {
            aspect-ratio: 4/3;
            border-radius: 10px;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2.5rem;
            opacity: 0.7;
        }
        .mock-img-row {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 8px;
        }
        .mock-img-thumb {
            aspect-ratio: 1;
            border-radius: 6px;
            border: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1rem;
            background: rgba(255,255,255,0.02);
        }
        .mock-form {
            display: flex;
            flex-direction: column;
            gap: 14px;
        }
        .mock-field {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        .mock-label {
            font-size: 0.7rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }
        .mock-input {
            padding: 9px 12px;
            border-radius: 8px;
            border: 1px solid var(--border);
            background: rgba(255,255,255,0.03);
            color: var(--text);
            font-size: 0.85rem;
            font-family: inherit;
        }
        .mock-input.title-input {
            font-weight: 600;
            font-size: 0.95rem;
        }
        .mock-textarea {
            padding: 9px 12px;
            border-radius: 8px;
            border: 1px solid var(--border);
            background: rgba(255,255,255,0.03);
            color: var(--text-secondary);
            font-size: 0.8rem;
            line-height: 1.5;
            min-height: 72px;
            font-family: inherit;
        }
        .mock-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }
        .mock-actions {
            display: flex;
            gap: 8px;
            margin-top: auto;
        }
        .mock-btn {
            padding: 10px 18px;
            border-radius: 8px;
            font-size: 0.8rem;
            font-weight: 600;
            border: 1px solid var(--border);
            background: var(--bg-raised);
            color: var(--text-secondary);
        }
        .mock-btn.publish {
            background: var(--accent);
            border-color: var(--accent);
            color: #fff;
            flex: 1;
        }
        .mock-statusbar {
            grid-column: 1 / -1;
            padding: 10px 18px;
            border-top: 1px solid var(--border);
            background: #0a0a0d;
            font-size: 0.75rem;
            color: var(--text-muted);
            display: flex;
            gap: 20px;
        }
        .mock-statusbar span {
            display: flex;
            align-items: center;
            gap: 5px;
        }

        /* ── Trust bar ── */
        .trust-bar {
            padding: 48px 0;
            border-top: 1px solid rgba(255,255,255,0.04);
            border-bottom: 1px solid rgba(255,255,255,0.04);
        }
        .trust-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1px;
            background: var(--border);
            border-radius: var(--radius);
            overflow: hidden;
        }
        .trust-item {
            padding: 28px 24px;
            text-align: center;
            background: var(--bg);
        }
        .trust-value {
            font-size: 1.5rem;
            font-weight: 800;
            margin-bottom: 4px;
            letter-spacing: -0.02em;
        }
        .trust-value.blue { color: var(--accent); }
        .trust-value.green { color: var(--green); }
        .trust-value.orange { color: var(--orange); }
        .trust-value.purple { color: var(--purple); }
        .trust-label {
            font-size: 0.82rem;
            color: var(--text-muted);
        }

        /* ── Section styling ── */
        .section {
            padding: 80px 0;
        }
        .section-header {
            text-align: center;
            max-width: 600px;
            margin: 0 auto 48px;
        }
        .section-label {
            display: inline-block;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--accent);
            margin-bottom: 12px;
            font-family: "JetBrains Mono", monospace;
        }
        .section-title {
            font-size: clamp(1.75rem, 3.5vw, 2.5rem);
            font-weight: 800;
            letter-spacing: -0.02em;
            line-height: 1.15;
            margin-bottom: 14px;
        }
        .section-desc {
            font-size: 1.05rem;
            color: var(--text-secondary);
            line-height: 1.7;
        }

        /* ── How It Works ── */
        .steps-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 2px;
            background: var(--border);
            border-radius: var(--radius);
            overflow: hidden;
        }
        .step {
            padding: 32px 24px;
            background: var(--bg);
            text-align: center;
            position: relative;
        }
        .step-number {
            width: 40px; height: 40px;
            border-radius: 10px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 1rem;
            margin-bottom: 16px;
        }
        .step:nth-child(1) .step-number { background: var(--accent-glow); color: var(--accent); border: 1px solid rgba(59,130,246,0.3); }
        .step:nth-child(2) .step-number { background: var(--purple-glow); color: var(--purple); border: 1px solid rgba(168,85,247,0.3); }
        .step:nth-child(3) .step-number { background: var(--orange-glow); color: var(--orange); border: 1px solid rgba(249,115,22,0.3); }
        .step:nth-child(4) .step-number { background: var(--green-glow); color: var(--green); border: 1px solid rgba(34,197,94,0.3); }
        .step-icon {
            font-size: 2rem;
            margin-bottom: 10px;
            display: block;
        }
        .step h3 {
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 8px;
            letter-spacing: -0.01em;
        }
        .step p {
            font-size: 0.85rem;
            color: var(--text-secondary);
            line-height: 1.6;
        }
        .step-arrow {
            position: absolute;
            right: -14px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            font-size: 1.2rem;
            z-index: 2;
        }

        /* ── Features ── */
        .features-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
        }
        .feature-card {
            padding: 28px 24px;
            border: 1px solid var(--border);
            border-radius: var(--radius);
            background: var(--bg-raised);
            transition: all 0.2s;
        }
        .feature-card:hover {
            border-color: var(--border-light);
            background: var(--bg-card);
            transform: translateY(-2px);
            box-shadow: var(--shadow-md);
        }
        .feature-icon {
            width: 44px; height: 44px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.3rem;
            margin-bottom: 16px;
        }
        .fi-blue { background: var(--accent-glow); border: 1px solid rgba(59,130,246,0.2); }
        .fi-green { background: var(--green-glow); border: 1px solid rgba(34,197,94,0.2); }
        .fi-orange { background: var(--orange-glow); border: 1px solid rgba(249,115,22,0.2); }
        .fi-purple { background: var(--purple-glow); border: 1px solid rgba(168,85,247,0.2); }
        .feature-card h3 {
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 8px;
            letter-spacing: -0.01em;
        }
        .feature-card p {
            font-size: 0.88rem;
            color: var(--text-secondary);
            line-height: 1.6;
        }
        .feature-tag {
            display: inline-block;
            margin-top: 12px;
            font-size: 0.7rem;
            font-weight: 600;
            font-family: "JetBrains Mono", monospace;
            padding: 3px 10px;
            border-radius: 999px;
            border: 1px solid var(--border);
            color: var(--text-muted);
        }
        .feature-card.featured {
            grid-column: span 2;
            background: linear-gradient(135deg, rgba(59,130,246,0.08), rgba(168,85,247,0.06));
            border-color: rgba(59,130,246,0.2);
        }
        .feature-card.featured:hover {
            border-color: rgba(59,130,246,0.35);
        }

        /* ── Screenshots section ── */
        .screenshots-section {
            padding: 80px 0;
            background: var(--bg-raised);
            border-top: 1px solid var(--border);
            border-bottom: 1px solid var(--border);
        }
        .screenshot-tabs {
            display: flex;
            justify-content: center;
            gap: 4px;
            margin-bottom: 36px;
            background: var(--bg);
            border-radius: 12px;
            padding: 4px;
            width: fit-content;
            margin-left: auto;
            margin-right: auto;
            border: 1px solid var(--border);
        }
        .screenshot-tabs input[type="radio"] { display: none; }
        .screenshot-tabs label {
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.15s;
        }
        .screenshot-tabs input[type="radio"]:checked + label {
            background: var(--accent);
            color: #fff;
        }
        .tab-content { display: none; }
        #tab-editor:checked ~ .tab-panels .panel-editor,
        #tab-admin:checked ~ .tab-panels .panel-admin,
        #tab-mobile:checked ~ .tab-panels .panel-mobile { display: block; }

        /* ── Admin showcase ── */
        .admin-showcase-window {
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border);
            background: #111114;
            box-shadow: var(--shadow-lg);
            max-width: 900px;
            margin: 0 auto;
        }
        .admin-mock-body {
            padding: 20px;
            min-height: 300px;
        }
        .admin-mock-tabs {
            display: flex;
            gap: 2px;
            margin-bottom: 16px;
            background: var(--border);
            border-radius: 8px;
            overflow: hidden;
        }
        .admin-mock-tab {
            padding: 8px 14px;
            font-size: 0.72rem;
            font-weight: 600;
            background: var(--bg-raised);
            color: var(--text-muted);
            flex: 1;
            text-align: center;
        }
        .admin-mock-tab.active {
            background: var(--accent);
            color: #fff;
        }
        .admin-mock-chat {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .chat-bubble {
            padding: 12px 16px;
            border-radius: 12px;
            font-size: 0.82rem;
            line-height: 1.5;
            max-width: 80%;
        }
        .chat-user {
            background: var(--accent);
            color: #fff;
            align-self: flex-end;
            border-bottom-right-radius: 4px;
        }
        .chat-bot {
            background: var(--bg-card);
            color: var(--text-secondary);
            border: 1px solid var(--border);
            align-self: flex-start;
            border-bottom-left-radius: 4px;
        }
        .chat-entry {
            display: flex;
            gap: 8px;
            align-items: center;
            padding: 6px 10px;
            background: rgba(34,197,94,0.1);
            border: 1px solid rgba(34,197,94,0.2);
            border-radius: 6px;
            font-size: 0.78rem;
            color: var(--green);
            font-weight: 500;
        }

        /* ── Mobile mockup ── */
        .phone-frame {
            width: 280px;
            margin: 0 auto;
            border-radius: 36px;
            border: 3px solid #333;
            background: #111;
            padding: 12px;
            box-shadow: var(--shadow-lg);
        }
        .phone-notch {
            width: 100px;
            height: 24px;
            background: #111;
            border-radius: 0 0 16px 16px;
            margin: -12px auto 8px;
        }
        .phone-screen {
            border-radius: 24px;
            overflow: hidden;
            background: #0d1117;
        }
        .phone-header {
            padding: 14px 16px;
            text-align: center;
            background: linear-gradient(180deg, #111827, #0d1117);
            border-bottom: 1px solid var(--border);
        }
        .phone-header h4 {
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--text);
        }
        .phone-camera-area {
            padding: 20px 16px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 14px;
        }
        .phone-viewfinder {
            width: 100%;
            aspect-ratio: 3/4;
            border-radius: 12px;
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            border: 2px dashed rgba(59,130,246,0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2.5rem;
        }
        .phone-shutter {
            width: 56px; height: 56px;
            border-radius: 50%;
            border: 3px solid #fff;
            background: transparent;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .phone-shutter-inner {
            width: 44px; height: 44px;
            border-radius: 50%;
            background: #fff;
        }
        .phone-thumbs {
            display: flex;
            gap: 6px;
        }
        .phone-thumb {
            width: 40px; height: 40px;
            border-radius: 6px;
            background: rgba(255,255,255,0.08);
            border: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.8rem;
        }

        /* ── Business section ── */
        .biz-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }
        .biz-card {
            padding: 24px;
            border: 1px solid var(--border);
            border-radius: var(--radius);
            background: var(--bg-raised);
        }
        .biz-card h3 {
            font-size: 0.95rem;
            font-weight: 700;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .biz-card p {
            font-size: 0.85rem;
            color: var(--text-secondary);
            line-height: 1.6;
        }

        /* ── Setup section ── */
        .setup-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 16px;
        }
        .setup-card {
            padding: 28px 24px;
            border: 1px solid var(--border);
            border-radius: var(--radius);
            background: var(--bg-raised);
            text-align: center;
        }
        .setup-step-num {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 32px; height: 32px;
            border-radius: 8px;
            background: var(--accent-glow);
            border: 1px solid rgba(59,130,246,0.3);
            color: var(--accent);
            font-weight: 800;
            font-size: 0.85rem;
            margin-bottom: 14px;
        }
        .setup-card h3 {
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 8px;
        }
        .setup-card p {
            font-size: 0.85rem;
            color: var(--text-secondary);
            line-height: 1.6;
        }
        .setup-card code {
            display: inline-block;
            margin-top: 10px;
            padding: 3px 8px;
            border-radius: 4px;
            background: rgba(255,255,255,0.06);
            font-size: 0.78rem;
            font-family: "JetBrains Mono", monospace;
            color: var(--text-muted);
        }

        /* ── Requirements ── */
        .req-table {
            width: 100%;
            border-collapse: collapse;
            border: 1px solid var(--border);
            border-radius: var(--radius);
            overflow: hidden;
        }
        .req-table th, .req-table td {
            padding: 14px 20px;
            text-align: left;
            font-size: 0.88rem;
            border-bottom: 1px solid var(--border);
        }
        .req-table th {
            background: var(--bg-raised);
            font-weight: 600;
            color: var(--text-secondary);
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }
        .req-table td {
            color: var(--text-secondary);
        }
        .req-table td:first-child {
            font-weight: 600;
            color: var(--text);
        }
        .req-table tr:last-child td { border-bottom: none; }

        /* ── FAQ ── */
        .faq-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            max-width: 900px;
            margin: 0 auto;
        }
        .faq-item {
            padding: 24px;
            border: 1px solid var(--border);
            border-radius: var(--radius);
            background: var(--bg-raised);
        }
        .faq-item h3 {
            font-size: 0.95rem;
            font-weight: 700;
            margin-bottom: 8px;
        }
        .faq-item p {
            font-size: 0.85rem;
            color: var(--text-secondary);
            line-height: 1.6;
        }

        /* ── Download CTA ── */
        .cta-section {
            padding: 80px 0;
            text-align: center;
        }
        .cta-box {
            padding: 56px 40px;
            border-radius: 20px;
            background: linear-gradient(135deg, rgba(59,130,246,0.1), rgba(168,85,247,0.08));
            border: 1px solid rgba(59,130,246,0.2);
        }
        .cta-box h2 {
            font-size: clamp(1.5rem, 3vw, 2.2rem);
            font-weight: 800;
            margin-bottom: 12px;
            letter-spacing: -0.02em;
        }
        .cta-box p {
            font-size: 1rem;
            color: var(--text-secondary);
            margin-bottom: 28px;
            max-width: 500px;
            margin-left: auto;
            margin-right: auto;
        }
        .download-grid {
            display: flex;
            justify-content: center;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 16px;
        }
        .dl-btn {
            display: inline-flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            min-width: 220px;
            padding: 14px 20px;
            border-radius: 12px;
            text-decoration: none;
            font-size: 0.9rem;
            font-weight: 600;
            transition: all 0.2s;
        }
        .dl-btn-active {
            background: var(--accent);
            color: #fff;
            border: 1px solid var(--accent);
        }
        .dl-btn-active:hover {
            background: var(--accent-hover);
            transform: translateY(-1px);
        }
        .dl-btn-disabled {
            background: rgba(255,255,255,0.03);
            color: var(--text-muted);
            border: 1px dashed var(--border);
            cursor: default;
        }
        .dl-pill {
            font-size: 0.65rem;
            font-weight: 600;
            font-family: "JetBrains Mono", monospace;
            padding: 3px 8px;
            border-radius: 999px;
        }
        .dl-pill.live {
            background: rgba(34,197,94,0.15);
            color: var(--green);
            border: 1px solid rgba(34,197,94,0.3);
        }
        .dl-pill.soon {
            background: rgba(234,179,8,0.1);
            color: var(--yellow);
            border: 1px solid rgba(234,179,8,0.2);
        }

        /* ── Dynamic content ── */
        .dynamic-section {
            padding: 60px 0;
            border-top: 1px solid var(--border);
        }
        .dynamic-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 14px;
            margin-top: 20px;
        }
        .dynamic-card {
            padding: 22px;
            border: 1px solid var(--border);
            border-radius: var(--radius);
            background: var(--bg-raised);
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .dynamic-card-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .dynamic-card h3 {
            font-size: 0.98rem;
            font-weight: 700;
        }
        .dynamic-card .item-summary {
            font-size: 0.88rem;
            color: #bed0ef;
        }
        .dynamic-card .item-content {
            font-size: 0.85rem;
            color: var(--text-secondary);
            line-height: 1.6;
        }
        .dynamic-card .item-link {
            margin-top: auto;
            font-size: 0.82rem;
            color: var(--accent);
            text-decoration: none;
            font-family: "JetBrains Mono", monospace;
        }

        /* ── Contact ── */
        .contact-section {
            padding: 60px 0;
            border-top: 1px solid var(--border);
        }
        .contact-layout {
            display: grid;
            grid-template-columns: 1fr 1.3fr;
            gap: 24px;
            max-width: 800px;
            margin: 0 auto;
        }
        .contact-info {
            padding: 24px;
            border: 1px solid var(--border);
            border-radius: var(--radius);
            background: var(--bg-raised);
        }
        .contact-info h3 {
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 12px;
        }
        .contact-info p {
            font-size: 0.88rem;
            color: var(--text-secondary);
            line-height: 1.7;
            margin-bottom: 8px;
        }
        .contact-form {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .contact-form label {
            display: flex;
            flex-direction: column;
            gap: 5px;
            font-size: 0.82rem;
            font-weight: 500;
            color: var(--text-secondary);
        }
        .contact-form input[type="text"],
        .contact-form input[type="email"],
        .contact-form textarea {
            padding: 10px 14px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border);
            background: var(--bg-raised);
            color: var(--text);
            font-family: inherit;
            font-size: 0.9rem;
            transition: border-color 0.15s;
        }
        .contact-form input:focus,
        .contact-form textarea:focus {
            outline: none;
            border-color: var(--accent);
        }
        .contact-form textarea {
            min-height: 100px;
            resize: vertical;
        }
        .contact-form .btn-primary {
            align-self: flex-start;
        }

        /* ── Flash messages ── */
        .flash {
            padding: 12px 16px;
            border-radius: var(--radius-sm);
            font-size: 0.9rem;
            margin-bottom: 16px;
        }
        .flash.success {
            background: rgba(34,197,94,0.1);
            border: 1px solid rgba(34,197,94,0.3);
            color: #86efac;
        }
        .flash.error {
            background: rgba(239,68,68,0.1);
            border: 1px solid rgba(239,68,68,0.3);
            color: #fca5a5;
        }

        /* ── Footer ── */
        .site-footer {
            padding: 40px 0;
            border-top: 1px solid var(--border);
            text-align: center;
        }
        .footer-content {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 12px;
        }
        .footer-brand {
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: 700;
            font-size: 0.95rem;
        }
        .footer-brand .nav-logo {
            width: 24px; height: 24px;
            font-size: 10px;
            border-radius: 6px;
        }
        .footer-note {
            font-size: 0.82rem;
            color: var(--text-muted);
            max-width: 400px;
            line-height: 1.5;
        }
        .footer-links {
            display: flex;
            gap: 16px;
            list-style: none;
        }
        .footer-links a {
            font-size: 0.8rem;
            color: var(--text-muted);
            text-decoration: none;
        }
        .footer-links a:hover { color: var(--text-secondary); }

        /* ── Admin mode (preserved) ── */
        body.admin-mode {
            font-family: "Inter", -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--admin-bg);
            color: var(--admin-text);
            min-height: 100vh;
            -webkit-font-smoothing: antialiased;
        }
        .admin-wrap {
            width: min(1240px, calc(100% - 40px));
            margin: 20px auto 40px;
        }
        .admin-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 14px;
            margin-bottom: 14px;
        }
        .admin-top h1 { margin: 0; font-size: 1.9rem; line-height: 1.1; }
        .admin-top p { margin: 4px 0 0; color: #59667d; }
        .admin-shell {
            display: grid;
            grid-template-columns: 250px 1fr;
            gap: 14px;
        }
        .admin-nav, .admin-panel {
            background: var(--admin-card);
            border: 1px solid var(--admin-line);
            border-radius: 14px;
            box-shadow: 0 10px 24px rgba(21,30,45,0.08);
        }
        .admin-nav {
            padding: 14px;
            position: sticky;
            top: 16px;
            height: fit-content;
        }
        .admin-nav a {
            display: block;
            color: #1d3b66;
            text-decoration: none;
            border-radius: 8px;
            padding: 9px 10px;
            margin-bottom: 6px;
            font-size: 0.93rem;
        }
        .admin-nav a:hover { background: #edf3ff; }
        .admin-main { display: grid; gap: 14px; }
        .admin-panel { padding: 16px; }
        .admin-panel h2 { margin: 0 0 12px; font-size: 1.2rem; }
        .admin-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .admin-grid-3 { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 10px; }
        .admin-input, .admin-textarea, .admin-select {
            width: 100%;
            border: 1px solid #c8d4e7;
            border-radius: 9px;
            padding: 9px 10px;
            background: #fff;
            color: #102340;
            font-family: inherit;
            font-size: 0.92rem;
        }
        .admin-textarea { min-height: 82px; resize: vertical; }
        .admin-label { display: grid; gap: 6px; color: #56698c; font-size: 0.82rem; }
        .admin-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
        .admin-btn {
            border: 0;
            border-radius: 9px;
            padding: 9px 12px;
            font-weight: 600;
            cursor: pointer;
            color: #fff;
            background: #235ecf;
        }
        .admin-btn.secondary { background: #5c708f; }
        .admin-btn.danger { background: #be3d4d; }
        .admin-list { margin: 0; padding: 0; list-style: none; display: grid; gap: 10px; }
        .admin-list-item {
            border: 1px solid #d8e1ef;
            border-radius: 10px;
            padding: 10px;
            background: #fbfdff;
        }
        .admin-list-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            gap: 8px;
        }
        .tag {
            display: inline-block;
            border-radius: 999px;
            font-family: "JetBrains Mono", monospace;
            font-size: 0.72rem;
            padding: 3px 8px;
            border: 1px solid #c5d2e6;
            color: #334b72;
        }
        .tag.unread { border-color: #ffb873; color: #9b5a0f; }
        .admin-login {
            width: min(480px, calc(100% - 40px));
            margin: 8vh auto;
            background: var(--admin-card);
            border: 1px solid var(--admin-line);
            border-radius: 14px;
            box-shadow: 0 12px 28px rgba(20,31,47,0.1);
            padding: 20px;
        }
        .admin-login h1 { margin: 0 0 8px; font-size: 1.5rem; line-height: 1.2; }
        .admin-login p { margin: 0 0 14px; color: #5e6c83; }
        .admin-login .form-grid { display: grid; gap: 10px; }
        .admin-login label { display: grid; gap: 6px; font-size: 0.86rem; color: #56698c; }
        .admin-login input[type="text"],
        .admin-login input[type="password"] {
            width: 100%;
            border: 1px solid #c8d4e7;
            border-radius: 9px;
            padding: 10px 11px;
            background: #fff;
            color: #102340;
            font-family: inherit;
            font-size: 0.95rem;
        }
        .btn {
            border: 0;
            border-radius: 11px;
            padding: 10px 13px;
            cursor: pointer;
            color: #fff;
            background: linear-gradient(120deg, #1f94c0, #2375ce);
            font-weight: 600;
            letter-spacing: 0.01em;
        }
        .warn-box {
            border: 1px solid #f0c576;
            background: #fff8e9;
            color: #8a5a00;
            border-radius: 10px;
            padding: 10px 12px;
            margin-bottom: 12px;
            font-size: 0.9rem;
        }

        /* ── Responsive ── */
        @media (max-width: 980px) {
            .window-body { grid-template-columns: 1fr; }
            .mock-sidebar { display: none; }
            .mock-main { grid-template-columns: 1fr; }
            .features-grid,
            .dynamic-grid { grid-template-columns: 1fr 1fr; }
            .feature-card.featured { grid-column: span 2; }
            .steps-grid { grid-template-columns: 1fr 1fr; }
            .step-arrow { display: none; }
            .biz-grid { grid-template-columns: 1fr; }
            .setup-grid { grid-template-columns: 1fr; }
            .faq-grid { grid-template-columns: 1fr; }
            .trust-grid { grid-template-columns: 1fr 1fr; }
            .contact-layout { grid-template-columns: 1fr; }
            .admin-shell { grid-template-columns: 1fr; }
            .admin-grid-2, .admin-grid-3 { grid-template-columns: 1fr; }
        }
        @media (max-width: 640px) {
            .container { padding: 0 16px; }
            .hero { padding: 50px 0 40px; }
            .section { padding: 50px 0; }
            .features-grid,
            .steps-grid,
            .dynamic-grid,
            .trust-grid { grid-template-columns: 1fr; }
            .feature-card.featured { grid-column: span 1; }
            .hero-actions { flex-direction: column; align-items: center; }
            .nav-links { gap: 4px; }
            .nav-links a { padding: 8px 10px; font-size: 0.8rem; }
            .download-grid { flex-direction: column; align-items: center; }
        }
    </style>
</head>
<body class="<?= $isAdminView ? 'admin-mode' : 'site-mode' ?>">
<?php if (!$isAdminView): ?>
<div class="hero-bg">
    <div class="container">

        <!-- Navigation -->
        <nav class="site-nav">
            <a class="nav-brand" href="./">
                <div class="nav-logo">m</div>
                <span class="nav-wordmark"><?= e(get_setting($settings, 'site_title', "myBay")) ?></span>
            </a>
            <ul class="nav-links">
                <li><a href="#features">Features</a></li>
                <li><a href="#how-it-works">How It Works</a></li>
                <li><a href="#setup">Setup</a></li>
                <li><a href="#download" class="nav-cta">Download</a></li>
            </ul>
        </nav>

        <!-- Hero -->
        <section class="hero">
            <div class="hero-badge">
                <span class="dot"></span>
                Open source &middot; MIT License &middot; Free local AI &middot; Production-ready
            </div>

            <h1><?= e(get_setting($settings, 'hero_heading', 'eBay listings in under 60 seconds.')) ?></h1>

            <p class="hero-sub"><?= e(get_setting($settings, 'hero_subheading', 'Snap photos on your phone, let AI do the rest. myBay turns iPhone photos into complete, published eBay listings with one click. Built for real sellers who want speed without losing quality.')) ?></p>

            <div class="hero-actions">
                <a href="#download" class="btn-primary">Download myBay</a>
                <a href="#how-it-works" class="btn-secondary">See how it works</a>
            </div>
            <p class="hero-note">macOS, Windows, Linux &middot; Free &middot; No account required</p>
        </section>

        <!-- App Mockup -->
        <div class="mockup-container">
            <div class="app-window">
                <div class="window-bar">
                    <span class="window-dot r"></span>
                    <span class="window-dot y"></span>
                    <span class="window-dot g"></span>
                    <span class="window-title">myBay &mdash; Listing Editor</span>
                </div>
                <div class="window-body">
                    <div class="mock-sidebar">
                        <div class="mock-sidebar-title">Draft Queue</div>
                        <div class="mock-draft active">
                            <div class="mock-draft-title">Vintage Polaroid Camera</div>
                            <div class="mock-draft-price">$45.00</div>
                            <div class="mock-confidence"><div class="mock-confidence-fill" style="width:92%"></div></div>
                        </div>
                        <div class="mock-draft">
                            <div class="mock-draft-title">Nike Air Max 90</div>
                            <div class="mock-draft-price">$89.99</div>
                            <div class="mock-confidence"><div class="mock-confidence-fill" style="width:88%"></div></div>
                        </div>
                        <div class="mock-draft">
                            <div class="mock-draft-title">Vintage Levi's 501</div>
                            <div class="mock-draft-price">$34.00</div>
                            <div class="mock-confidence"><div class="mock-confidence-fill" style="width:95%"></div></div>
                        </div>
                        <div class="mock-draft">
                            <div class="mock-draft-title">KitchenAid Mixer</div>
                            <div class="mock-draft-price">$120.00</div>
                            <div class="mock-confidence"><div class="mock-confidence-fill" style="width:84%"></div></div>
                        </div>
                    </div>
                    <div class="mock-main">
                        <div class="mock-images">
                            <div class="mock-img-placeholder">&#128247;</div>
                            <div class="mock-img-row">
                                <div class="mock-img-thumb">&#128247;</div>
                                <div class="mock-img-thumb">&#128247;</div>
                                <div class="mock-img-thumb">+</div>
                            </div>
                        </div>
                        <div class="mock-form">
                            <div class="mock-field">
                                <div class="mock-label">Title</div>
                                <div class="mock-input title-input">Vintage Polaroid OneStep Close-Up 600 Camera</div>
                            </div>
                            <div class="mock-row">
                                <div class="mock-field">
                                    <div class="mock-label">Category</div>
                                    <div class="mock-input">Cameras &amp; Photo</div>
                                </div>
                                <div class="mock-field">
                                    <div class="mock-label">Condition</div>
                                    <div class="mock-input">Used - Very Good</div>
                                </div>
                            </div>
                            <div class="mock-row">
                                <div class="mock-field">
                                    <div class="mock-label">Price</div>
                                    <div class="mock-input" style="color: var(--green); font-weight:700;">$45.00</div>
                                </div>
                                <div class="mock-field">
                                    <div class="mock-label">AI Confidence</div>
                                    <div class="mock-input" style="color: var(--accent);">92% &mdash; High</div>
                                </div>
                            </div>
                            <div class="mock-field">
                                <div class="mock-label">Description</div>
                                <div class="mock-textarea">Great condition vintage Polaroid OneStep camera with close-up lens. Tested and working. Comes with original strap. Film not included.</div>
                            </div>
                            <div class="mock-actions">
                                <div class="mock-btn">Save</div>
                                <div class="mock-btn">Delete</div>
                                <div class="mock-btn publish">Publish to eBay</div>
                            </div>
                        </div>
                        <div class="mock-statusbar">
                            <span>&#9679; Today: 12 listed</span>
                            <span>&#9679; 3 sold</span>
                            <span>&#9679; $247 revenue</span>
                            <span>&#9679; 48 min saved</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Trust Bar -->
<section class="trust-bar">
    <div class="container">
        <div class="trust-grid">
            <div class="trust-item">
                <div class="trust-value blue">&lt; 60s</div>
                <div class="trust-label">Photo to live listing</div>
            </div>
            <div class="trust-item">
                <div class="trust-value green">AI-Powered</div>
                <div class="trust-label">OpenAI vision + web search</div>
            </div>
            <div class="trust-item">
                <div class="trust-value purple">Local-First</div>
                <div class="trust-label">Your data stays on your machine</div>
            </div>
            <div class="trust-item">
                <div class="trust-value orange">Open Source</div>
                <div class="trust-label">MIT License &middot; Free forever</div>
            </div>
        </div>
    </div>
</section>

<?php if ($flash): ?>
    <div class="container">
        <div class="flash <?= e((string) $flash['type']) ?>" style="margin-top:20px;">
            <?= e((string) $flash['message']) ?>
        </div>
    </div>
<?php endif; ?>

<!-- How It Works -->
<section class="section" id="how-it-works">
    <div class="container">
        <div class="section-header">
            <div class="section-label">How It Works</div>
            <h2 class="section-title">From photo to listing in four steps</h2>
            <p class="section-desc">No manual data entry. No copy-pasting from other listings. Just snap and sell.</p>
        </div>
        <div class="steps-grid">
            <div class="step">
                <div class="step-icon">&#128247;</div>
                <div class="step-number">1</div>
                <h3>Snap Photos</h3>
                <p>Scan the QR code with your phone. Take 1-3 photos of your item. Photos transfer to your desktop instantly over WiFi.</p>
                <span class="step-arrow">&#8594;</span>
            </div>
            <div class="step">
                <div class="step-icon">&#129302;</div>
                <div class="step-number">2</div>
                <h3>AI Analyzes</h3>
                <p>OpenAI identifies the product, generates a title, description, category, condition, and researches current market prices.</p>
                <span class="step-arrow">&#8594;</span>
            </div>
            <div class="step">
                <div class="step-icon">&#9998;</div>
                <div class="step-number">3</div>
                <h3>Review &amp; Edit</h3>
                <p>Everything appears in your draft queue. Tweak the title, adjust the price, or let Turbo Mode auto-publish high-confidence items.</p>
                <span class="step-arrow">&#8594;</span>
            </div>
            <div class="step">
                <div class="step-icon">&#128640;</div>
                <div class="step-number">4</div>
                <h3>Publish</h3>
                <p>One click uploads images to eBay and creates the listing. Verified via eBay API with a direct link to your live listing.</p>
            </div>
        </div>
    </div>
</section>

<!-- Features -->
<section class="section" id="features" style="padding-top:40px;">
    <div class="container">
        <div class="section-header">
            <div class="section-label">Features</div>
            <h2 class="section-title">Everything you need to list fast and run the business</h2>
            <p class="section-desc">myBay handles listing creation and business management in one app.</p>
        </div>
        <div class="features-grid">
            <div class="feature-card featured">
                <div class="feature-icon fi-blue">&#129302;</div>
                <h3>AI Vision + Web Search</h3>
                <p>Analyze product photos with OpenAI (cloud, best quality + web search pricing) or Ollama (free, local, fully private). Both generate eBay-optimized titles, descriptions, and pricing. Uses strict JSON schema validation so output is always clean and structured.</p>
                <span class="feature-tag">OpenAI or Ollama</span>
            </div>
            <div class="feature-card">
                <div class="feature-icon fi-green">&#128241;</div>
                <h3>Phone Camera Integration</h3>
                <p>Scan a QR code to open the camera on your phone. Photos go straight to your desktop over WiFi. No cables, no AirDrop, no file management.</p>
                <span class="feature-tag">QR + WebSocket</span>
            </div>
            <div class="feature-card">
                <div class="feature-icon fi-orange">&#9889;</div>
                <h3>Turbo Mode</h3>
                <p>High-confidence items auto-publish without review. Includes a 30-second undo window so nothing goes live that shouldn't.</p>
                <span class="feature-tag">Auto-Publish</span>
            </div>
            <div class="feature-card">
                <div class="feature-icon fi-purple">&#128176;</div>
                <h3>Smart Pricing</h3>
                <p>Compares your item against current eBay listings using the Browse API. Shows average, median, min, and max market prices.</p>
                <span class="feature-tag">Market Data</span>
            </div>
            <div class="feature-card">
                <div class="feature-icon fi-green">&#127912;</div>
                <h3>Background Removal</h3>
                <p>Automatic AI-powered background removal for professional white-background product photos. Optional &mdash; runs locally on your machine.</p>
                <span class="feature-tag">rembg</span>
            </div>
            <div class="feature-card">
                <div class="feature-icon fi-blue">&#128268;</div>
                <h3>Offline Support</h3>
                <p>Lost internet? Listings queue locally and auto-sync when your connection comes back. Never lose work.</p>
                <span class="feature-tag">Local Queue</span>
            </div>
            <div class="feature-card">
                <div class="feature-icon fi-orange">&#128737;</div>
                <h3>Publish Recovery</h3>
                <p>Handles invalid condition/category combos, duplicate offers, and missing item specifics automatically with retries and fallbacks.</p>
                <span class="feature-tag">Auto-Retry</span>
            </div>
            <div class="feature-card">
                <div class="feature-icon fi-purple">&#9989;</div>
                <h3>API Verification</h3>
                <p>After publishing, the app verifies your listing is live via eBay Browse API and gives you a direct link. No guesswork.</p>
                <span class="feature-tag">Verified</span>
            </div>
        </div>
    </div>
</section>

<!-- Screenshots / Tabs Section -->
<section class="screenshots-section" id="screenshots">
    <div class="container">
        <div class="section-header">
            <div class="section-label">App Preview</div>
            <h2 class="section-title">See it in action</h2>
            <p class="section-desc">Three interfaces, one seamless workflow.</p>
        </div>

        <div class="screenshot-tabs">
            <input type="radio" name="tab" id="tab-editor" checked>
            <label for="tab-editor">Listing Editor</label>
            <input type="radio" name="tab" id="tab-admin">
            <label for="tab-admin">Business Dashboard</label>
            <input type="radio" name="tab" id="tab-mobile">
            <label for="tab-mobile">Mobile Camera</label>

            <div class="tab-panels">
                <!-- Editor Panel (default shown) -->
                <div class="panel-editor tab-content">
                    <div class="admin-showcase-window" style="max-width:900px;margin:0 auto;">
                        <div class="window-bar">
                            <span class="window-dot r"></span>
                            <span class="window-dot y"></span>
                            <span class="window-dot g"></span>
                            <span class="window-title">myBay &mdash; Dashboard</span>
                        </div>
                        <div style="padding:24px; display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:12px;">
                            <div style="padding:16px; border-radius:10px; border:1px solid var(--border); background:var(--bg-card); text-align:center;">
                                <div style="font-size:1.8rem; font-weight:800; color:var(--accent);">12</div>
                                <div style="font-size:0.75rem; color:var(--text-muted);">Listed Today</div>
                            </div>
                            <div style="padding:16px; border-radius:10px; border:1px solid var(--border); background:var(--bg-card); text-align:center;">
                                <div style="font-size:1.8rem; font-weight:800; color:var(--green);">3</div>
                                <div style="font-size:0.75rem; color:var(--text-muted);">Sold Today</div>
                            </div>
                            <div style="padding:16px; border-radius:10px; border:1px solid var(--border); background:var(--bg-card); text-align:center;">
                                <div style="font-size:1.8rem; font-weight:800; color:var(--orange);">$247</div>
                                <div style="font-size:0.75rem; color:var(--text-muted);">Revenue</div>
                            </div>
                            <div style="padding:16px; border-radius:10px; border:1px solid var(--border); background:var(--bg-card); text-align:center;">
                                <div style="font-size:1.8rem; font-weight:800; color:var(--purple);">48m</div>
                                <div style="font-size:0.75rem; color:var(--text-muted);">Time Saved</div>
                            </div>
                        </div>
                        <div style="padding:0 24px 24px; display:grid; gap:8px;">
                            <div style="font-size:0.8rem; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.06em;">Recent Listings</div>
                            <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 14px; border-radius:8px; border:1px solid var(--border); background:var(--bg-card); font-size:0.82rem;">
                                <span style="color:var(--text);">Vintage Polaroid Camera</span>
                                <span style="color:var(--green); font-weight:600;">$45.00 &middot; Published</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 14px; border-radius:8px; border:1px solid var(--border); background:var(--bg-card); font-size:0.82rem;">
                                <span style="color:var(--text);">Nike Air Max 90 Size 10</span>
                                <span style="color:var(--green); font-weight:600;">$89.99 &middot; Published</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 14px; border-radius:8px; border:1px solid var(--border); background:var(--bg-card); font-size:0.82rem;">
                                <span style="color:var(--text);">KitchenAid Classic Stand Mixer</span>
                                <span style="color:var(--accent); font-weight:600;">$120.00 &middot; Draft</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Admin Panel -->
                <div class="panel-admin tab-content">
                    <div class="admin-showcase-window">
                        <div class="window-bar">
                            <span class="window-dot r"></span>
                            <span class="window-dot y"></span>
                            <span class="window-dot g"></span>
                            <span class="window-title">myBay &mdash; Admin Dashboard</span>
                        </div>
                        <div class="admin-mock-body">
                            <div class="admin-mock-tabs">
                                <div class="admin-mock-tab active">AI Assistant</div>
                                <div class="admin-mock-tab">Business Info</div>
                                <div class="admin-mock-tab">Expenses</div>
                                <div class="admin-mock-tab">Income</div>
                                <div class="admin-mock-tab">Mileage</div>
                                <div class="admin-mock-tab">Taxes</div>
                                <div class="admin-mock-tab">Export</div>
                            </div>
                            <div class="admin-mock-chat">
                                <div class="chat-bubble chat-user">spent $25 at goodwill on inventory, drove 12 miles</div>
                                <div class="chat-bubble chat-bot">
                                    Got it! Logged:<br><br>
                                    <div class="chat-entry" style="margin-top:6px;">&#10003; Expense: $25.00 (inventory) &mdash; Goodwill</div>
                                    <div class="chat-entry" style="margin-top:6px;">&#10003; Mileage: 12.0 mi &mdash; $8.40 deduction</div>
                                </div>
                                <div class="chat-bubble chat-user">sold a vintage camera for $85 on ebay, $11 in fees</div>
                                <div class="chat-bubble chat-bot">
                                    Logged:<br><br>
                                    <div class="chat-entry" style="margin-top:6px;">&#10003; Income: $85.00 (eBay) &mdash; $11.00 fees &mdash; $74.00 net</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Mobile Panel -->
                <div class="panel-mobile tab-content">
                    <div class="phone-frame">
                        <div class="phone-notch"></div>
                        <div class="phone-screen">
                            <div class="phone-header">
                                <h4>myBay Camera</h4>
                            </div>
                            <div class="phone-camera-area">
                                <div class="phone-viewfinder">&#128247;</div>
                                <div class="phone-shutter"><div class="phone-shutter-inner"></div></div>
                                <div class="phone-thumbs">
                                    <div class="phone-thumb">&#128247;</div>
                                    <div class="phone-thumb">&#128247;</div>
                                    <div class="phone-thumb">+</div>
                                </div>
                                <div style="font-size:0.72rem; color:var(--text-muted); text-align:center;">Take 1-3 photos &middot; Auto-uploads to desktop</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</section>

<!-- Business Backend -->
<section class="section" id="business">
    <div class="container">
        <div class="section-header">
            <div class="section-label">Business Backend</div>
            <h2 class="section-title">Run your sole proprietorship from one app</h2>
            <p class="section-desc">The Admin dashboard turns myBay into a full business management tool. Track everything you need for tax time.</p>
        </div>
        <div class="biz-grid">
            <div class="biz-card">
                <h3>&#128172; AI Business Assistant</h3>
                <p>Type plain English like "spent $25 at goodwill on inventory, drove 12 miles" and the AI logs expenses, income, and mileage automatically. One message can create multiple entries.</p>
            </div>
            <div class="biz-card">
                <h3>&#128184; Expense Tracking</h3>
                <p>Log expenses by category (inventory, shipping, eBay fees, supplies, storage, office). Attach receipt images. View YTD totals by category.</p>
            </div>
            <div class="biz-card">
                <h3>&#128181; Income Tracking</h3>
                <p>Manual entry or one-click import of sold eBay listings. Tracks platform fees, shipping costs, and sales tax separately. Calculates net automatically.</p>
            </div>
            <div class="biz-card">
                <h3>&#128663; Mileage Tracker</h3>
                <p>Log trips with IRS standard rate. Supports sourcing runs, post office trips, supply pickups. Auto-calculates deduction per trip and YTD totals.</p>
            </div>
            <div class="biz-card">
                <h3>&#128203; Tax Summary</h3>
                <p>Schedule C profit &amp; loss, home office deduction, self-employment tax estimate, quarterly estimated taxes (Federal + State), and 1099-K reconciliation.</p>
            </div>
            <div class="biz-card">
                <h3>&#128230; CSV Export</h3>
                <p>Export by date range. Individual CSVs or a bundled ZIP file with receipt images included. Hand it to your accountant or import into tax software.</p>
            </div>
        </div>
    </div>
</section>

<!-- Setup -->
<section class="section" id="setup" style="padding-bottom:40px;">
    <div class="container">
        <div class="section-header">
            <div class="section-label">Getting Started</div>
            <h2 class="section-title">Up and running in 5 minutes</h2>
            <p class="section-desc">Three things to set up, then you're listing.</p>
        </div>
        <div class="setup-grid">
            <div class="setup-card">
                <div class="setup-step-num">1</div>
                <h3>Set Up AI (Free or Paid)</h3>
                <p><strong>Free option:</strong> Install Ollama and pull a vision model &mdash; zero accounts, zero cost.<br><strong>Paid option:</strong> Get an OpenAI API key for best quality + web search pricing (~$0.01-0.05/listing).</p>
                <code>ollama pull qwen3.5:2b</code>
            </div>
            <div class="setup-card">
                <div class="setup-step-num">2</div>
                <h3>Create an eBay App</h3>
                <p>Register at developer.ebay.com, create an application, and note your Client ID, Client Secret, and RuName. Set redirect URL to localhost:8000.</p>
                <code>EBAY_APP_ID=your-app-id</code>
            </div>
            <div class="setup-card">
                <div class="setup-step-num">3</div>
                <h3>Install &amp; Connect</h3>
                <p>Download the app or run from source. The setup wizard walks you through connecting your eBay seller account via OAuth. Start listing immediately.</p>
                <code>python3 run.py --gui</code>
            </div>
        </div>
    </div>
</section>

<!-- Requirements -->
<section class="section" style="padding-top:20px;">
    <div class="container">
        <div class="section-header">
            <div class="section-label">Requirements</div>
            <h2 class="section-title">What you need</h2>
        </div>
        <table class="req-table">
            <thead>
                <tr>
                    <th>Requirement</th>
                    <th>Details</th>
                    <th>Cost</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Operating System</td>
                    <td>macOS 12+, Windows 10+, or Linux</td>
                    <td>&mdash;</td>
                </tr>
                <tr>
                    <td>AI Backend</td>
                    <td>Ollama (local, free) or OpenAI (cloud, best quality)</td>
                    <td>Free &ndash; $0.05/listing</td>
                </tr>
                <tr>
                    <td>eBay Seller Account</td>
                    <td>Regular eBay account with selling enabled</td>
                    <td>Free</td>
                </tr>
                <tr>
                    <td>eBay Developer Account</td>
                    <td>For API access. Individual tier (5,000 calls/day)</td>
                    <td>Free</td>
                </tr>
                <tr>
                    <td>Python 3.10+</td>
                    <td>Only if running from source (not needed for .dmg/.exe)</td>
                    <td>Free</td>
                </tr>
                <tr>
                    <td>Same WiFi Network</td>
                    <td>Phone and computer for camera features (or use ngrok for remote)</td>
                    <td>&mdash;</td>
                </tr>
            </tbody>
        </table>
    </div>
</section>

<!-- FAQ -->
<section class="section" id="faq">
    <div class="container">
        <div class="section-header">
            <div class="section-label">FAQ</div>
            <h2 class="section-title">Common questions</h2>
        </div>
        <div class="faq-grid">
            <div class="faq-item">
                <h3>How much does it cost to use?</h3>
                <p>myBay is free and open source. You pay only for OpenAI API usage (~$0.01-0.05 per listing) and standard eBay seller fees. No subscription, no hidden costs.</p>
            </div>
            <div class="faq-item">
                <h3>Is my data safe?</h3>
                <p>Everything runs locally on your machine. Your API keys, eBay tokens, and business data are stored locally and never leave your computer. The app is open source so you can verify this yourself.</p>
            </div>
            <div class="faq-item">
                <h3>What AI model does it use?</h3>
                <p>OpenAI GPT-5.4 Nano by default, with vision and web search capabilities. You can override the model via the OPENAI_VISION_MODEL environment variable.</p>
            </div>
            <div class="faq-item">
                <h3>Does it work with eBay Sandbox?</h3>
                <p>Yes. Start with Sandbox to test your setup, then switch to Production when you're ready to list real items. The app supports both environments.</p>
            </div>
            <div class="faq-item">
                <h3>Can I use it without a phone?</h3>
                <p>Yes. You can drag and drop images directly into the queue folder. The phone camera is just the fastest way to get photos in.</p>
            </div>
            <div class="faq-item">
                <h3>What if I'm offline?</h3>
                <p>Listings queue locally and auto-publish when your connection comes back. You'll never lose work due to a network interruption.</p>
            </div>
        </div>
    </div>
</section>

<!-- Dynamic Content from DB -->
<?php foreach ($publicCategories as $category): ?>
    <section class="dynamic-section" id="<?= e((string) $category['slug']) ?>">
        <div class="container">
            <div style="display:flex; align-items:baseline; justify-content:space-between; margin-bottom:6px;">
                <h2 class="section-title" style="text-align:left; font-size:1.5rem; margin-bottom:0;"><?= e((string) $category['name']) ?></h2>
                <span class="feature-tag"><?= e((string) $category['slug']) ?></span>
            </div>
            <?php if ((string) $category['description'] !== ''): ?>
                <p class="section-desc" style="text-align:left; margin-bottom:0;"><?= e((string) $category['description']) ?></p>
            <?php endif; ?>
            <div class="dynamic-grid">
                <?php $items = $publicItemsByCategory[(int) $category['id']] ?? []; ?>
                <?php if (count($items) === 0): ?>
                    <div class="dynamic-card">
                        <h3>No content yet</h3>
                        <p class="item-content">Add content blocks for this category in the admin backend.</p>
                    </div>
                <?php else: ?>
                    <?php foreach ($items as $item): ?>
                        <div class="dynamic-card">
                            <div class="dynamic-card-head">
                                <h3><?= e((string) $item['title']) ?></h3>
                                <?php if ((string) $item['badge'] !== ''): ?>
                                    <span class="feature-tag"><?= e((string) $item['badge']) ?></span>
                                <?php endif; ?>
                            </div>
                            <?php if ((string) $item['summary'] !== ''): ?>
                                <p class="item-summary"><?= e((string) $item['summary']) ?></p>
                            <?php endif; ?>
                            <?php if ((string) $item['content'] !== ''): ?>
                                <p class="item-content"><?= nl2br(e((string) $item['content'])) ?></p>
                            <?php endif; ?>
                            <?php
                                $publicCtaUrl = sanitize_url((string) $item['cta_url'], true);
                                $publicCtaLabel = trim((string) $item['cta_label']);
                            ?>
                            <?php if ($publicCtaUrl !== '' && $publicCtaLabel !== ''): ?>
                                <a class="item-link" href="<?= e($publicCtaUrl) ?>" target="_blank" rel="noopener">
                                    <?= e($publicCtaLabel) ?>
                                </a>
                            <?php endif; ?>
                        </div>
                    <?php endforeach; ?>
                <?php endif; ?>
            </div>
        </div>
    </section>
<?php endforeach; ?>

<!-- Download CTA -->
<section class="cta-section" id="download">
    <div class="container">
        <div class="cta-box">
            <h2>Ready to list faster?</h2>
            <p>Download myBay and start turning photos into eBay listings in under 60 seconds.</p>
            <div class="download-grid">
                <?php $macUrl = sanitize_url(get_setting($settings, 'mac_download_url', ''), true); ?>
                <?php if ($macUrl !== ''): ?>
                    <a class="dl-btn dl-btn-active" href="<?= e($macUrl) ?>" target="_blank" rel="noopener">
                        <span>Download for macOS</span>
                        <span class="dl-pill live">LIVE</span>
                    </a>
                <?php else: ?>
                    <div class="dl-btn dl-btn-disabled">
                        <span>macOS</span>
                        <span class="dl-pill soon">SET URL</span>
                    </div>
                <?php endif; ?>

                <?php $windowsUrl = sanitize_url(get_setting($settings, 'windows_download_url', ''), true); ?>
                <?php if ($windowsUrl !== ''): ?>
                    <a class="dl-btn dl-btn-active" href="<?= e($windowsUrl) ?>" target="_blank" rel="noopener">
                        <span>Download for Windows</span>
                        <span class="dl-pill live">LIVE</span>
                    </a>
                <?php else: ?>
                    <div class="dl-btn dl-btn-disabled">
                        <span>Windows</span>
                        <span class="dl-pill soon">SOON</span>
                    </div>
                <?php endif; ?>

                <?php $linuxUrl = sanitize_url(get_setting($settings, 'linux_download_url', ''), true); ?>
                <?php if ($linuxUrl !== ''): ?>
                    <a class="dl-btn dl-btn-active" href="<?= e($linuxUrl) ?>" target="_blank" rel="noopener">
                        <span>Download for Linux</span>
                        <span class="dl-pill live">LIVE</span>
                    </a>
                <?php else: ?>
                    <div class="dl-btn dl-btn-disabled">
                        <span>Linux</span>
                        <span class="dl-pill soon">SOON</span>
                    </div>
                <?php endif; ?>
            </div>
            <p style="font-size:0.8rem; color:var(--text-muted); margin-bottom:0;">Or run from source: <code style="padding:2px 6px; border-radius:4px; background:rgba(255,255,255,0.06); font-family:'JetBrains Mono',monospace; font-size:0.78rem;">git clone &amp;&amp; pip install -r requirements.txt &amp;&amp; python3 run.py --gui</code></p>
        </div>
    </div>
</section>

<!-- Contact -->
<section class="contact-section" id="contact">
    <div class="container">
        <div class="section-header">
            <div class="section-label">Contact</div>
            <h2 class="section-title">Get in touch</h2>
            <p class="section-desc">Questions, feedback, or just want to say hi? Drop a message.</p>
        </div>
        <div class="contact-layout">
            <div class="contact-info">
                <h3>Reach out</h3>
                <p><strong>Email:</strong> <?= e(get_setting($settings, 'contact_email', 'support@example.com')) ?></p>
                <p>Messages go directly to the admin inbox. Expect a reply within 24-48 hours.</p>
                <p style="margin-top:16px; padding-top:16px; border-top:1px solid var(--border);">
                    <strong>Open Source</strong><br>
                    Found a bug? Want to contribute? Check out the project on GitHub.
                </p>
            </div>
            <form method="post" class="contact-form">
                <input type="hidden" name="csrf_token" value="<?= e($csrf) ?>">
                <input type="hidden" name="action" value="contact_submit">
                <label>
                    Name
                    <input type="text" name="name" maxlength="120" required>
                </label>
                <label>
                    Email
                    <input type="email" name="email" maxlength="160" required>
                </label>
                <label>
                    Subject
                    <input type="text" name="subject" maxlength="200">
                </label>
                <label>
                    Message
                    <textarea name="message" maxlength="5000" required></textarea>
                </label>
                <button type="submit" class="btn-primary" style="padding:12px 24px;">Send message</button>
            </form>
        </div>
    </div>
</section>

<!-- Footer -->
<footer class="site-footer">
    <div class="container">
        <div class="footer-content">
            <div class="footer-brand">
                <div class="nav-logo">m</div>
                <span><?= e(get_setting($settings, 'site_title', "myBay")) ?></span>
            </div>
            <p class="footer-note"><?= e(get_setting($settings, 'footer_note', 'Built for real sellers. Focused on speed, reliability, and clean listings.')) ?></p>
            <ul class="footer-links">
                <li><a href="#features">Features</a></li>
                <li><a href="#how-it-works">How It Works</a></li>
                <li><a href="#download">Download</a></li>
                <li><a href="#contact">Contact</a></li>
                <li><a href="?admin=1">Admin</a></li>
            </ul>
        </div>
    </div>
</footer>

<?php else: ?>
    <?php if (!$isAdminAuthenticated): ?>
        <div class="admin-login">
            <h1>Landing Page Admin</h1>
            <p>Sign in to manage downloads, categories, content blocks, and contact messages.</p>
            <?php if ($flash): ?>
                <div class="flash <?= e((string) $flash['type']) ?>" style="margin: 0 0 10px;">
                    <?= e((string) $flash['message']) ?>
                </div>
            <?php endif; ?>
            <form method="post" class="form-grid">
                <input type="hidden" name="csrf_token" value="<?= e($csrf) ?>">
                <input type="hidden" name="action" value="admin_login">
                <label>
                    Username
                    <input type="text" name="username" autocomplete="username" required>
                </label>
                <label>
                    Password
                    <input type="password" name="password" autocomplete="current-password" required>
                </label>
                <button class="btn" type="submit">Sign in</button>
            </form>
            <p style="margin-top: 12px; color: #65758f; font-size: 0.86rem;">
                On first run, set a strong admin password using <code>LANDING_ADMIN_PASSWORD</code>. Default-password login is blocked for non-local access.
            </p>
        </div>
    <?php else: ?>
        <div class="admin-wrap">
            <div class="admin-top">
                <div>
                    <h1>Landing Page Backend</h1>
                    <p>Manage content and review inbound messages.</p>
                </div>
                <form method="post">
                    <input type="hidden" name="csrf_token" value="<?= e($csrf) ?>">
                    <input type="hidden" name="action" value="admin_logout">
                    <button class="admin-btn secondary" type="submit">Log out</button>
                </form>
            </div>

            <?php if ($flash): ?>
                <div class="flash <?= e((string) $flash['type']) ?>" style="margin: 0 0 12px;">
                    <?= e((string) $flash['message']) ?>
                </div>
            <?php endif; ?>

            <?php if ($usingDefaultPassword): ?>
                <div class="warn-box">
                    Default admin password is still active. Change it now in the Security section.
                </div>
            <?php endif; ?>

            <div class="admin-shell">
                <aside class="admin-nav">
                    <a href="#settings">Site Settings</a>
                    <a href="#categories">Categories</a>
                    <a href="#items">Content Blocks</a>
                    <a href="#messages">Messages</a>
                    <a href="#security">Security</a>
                    <a href="./">View Landing Page</a>
                </aside>

                <main class="admin-main">
                    <section class="admin-panel" id="settings">
                        <h2>Site Settings</h2>
                        <form method="post">
                            <input type="hidden" name="csrf_token" value="<?= e($csrf) ?>">
                            <input type="hidden" name="action" value="save_settings">
                            <div class="admin-grid-2">
                                <label class="admin-label">Site title
                                    <input class="admin-input" type="text" name="site_title" value="<?= e(get_setting($settings, 'site_title')) ?>">
                                </label>
                                <label class="admin-label">Site kicker
                                    <input class="admin-input" type="text" name="site_kicker" value="<?= e(get_setting($settings, 'site_kicker')) ?>">
                                </label>
                            </div>
                            <label class="admin-label">Hero heading
                                <input class="admin-input" type="text" name="hero_heading" value="<?= e(get_setting($settings, 'hero_heading')) ?>">
                            </label>
                            <label class="admin-label">Hero subheading
                                <textarea class="admin-textarea" name="hero_subheading"><?= e(get_setting($settings, 'hero_subheading')) ?></textarea>
                            </label>
                            <div class="admin-grid-3">
                                <label class="admin-label">macOS download URL
                                    <input class="admin-input" type="text" name="mac_download_url" value="<?= e(get_setting($settings, 'mac_download_url')) ?>" placeholder="https://... or /downloads/app.dmg">
                                </label>
                                <label class="admin-label">Windows download URL
                                    <input class="admin-input" type="text" name="windows_download_url" value="<?= e(get_setting($settings, 'windows_download_url')) ?>" placeholder="https://... or /downloads/app.exe">
                                </label>
                                <label class="admin-label">Linux download URL
                                    <input class="admin-input" type="text" name="linux_download_url" value="<?= e(get_setting($settings, 'linux_download_url')) ?>" placeholder="https://... or /downloads/app.AppImage">
                                </label>
                            </div>
                            <div class="admin-grid-2">
                                <label class="admin-label">Contact email
                                    <input class="admin-input" type="email" name="contact_email" value="<?= e(get_setting($settings, 'contact_email')) ?>">
                                </label>
                                <label class="admin-label">Footer note
                                    <input class="admin-input" type="text" name="footer_note" value="<?= e(get_setting($settings, 'footer_note')) ?>">
                                </label>
                            </div>
                            <div class="admin-actions">
                                <button class="admin-btn" type="submit">Save settings</button>
                            </div>
                        </form>
                    </section>

                    <section class="admin-panel" id="categories">
                        <h2>Categories</h2>
                        <form method="post">
                            <input type="hidden" name="csrf_token" value="<?= e($csrf) ?>">
                            <input type="hidden" name="action" value="add_category">
                            <div class="admin-grid-3">
                                <label class="admin-label">Name
                                    <input class="admin-input" type="text" name="name" required>
                                </label>
                                <label class="admin-label">Slug
                                    <input class="admin-input" type="text" name="slug" placeholder="optional-auto-from-name">
                                </label>
                                <label class="admin-label">Sort order
                                    <input class="admin-input" type="number" name="sort_order" value="100">
                                </label>
                            </div>
                            <label class="admin-label">Description
                                <input class="admin-input" type="text" name="description">
                            </label>
                            <label class="admin-label" style="display:inline-flex; align-items:center; gap:8px; margin-top:8px;">
                                <input type="checkbox" name="is_active" value="1" checked> Active on frontend
                            </label>
                            <div class="admin-actions">
                                <button class="admin-btn" type="submit">Add category</button>
                            </div>
                        </form>

                        <ul class="admin-list" style="margin-top:12px;">
                            <?php foreach ($adminCategories as $category): ?>
                                <li class="admin-list-item">
                                    <div class="admin-list-head">
                                        <strong><?= e((string) $category['name']) ?></strong>
                                        <span class="tag"><?= !empty($category['is_active']) ? 'active' : 'hidden' ?></span>
                                    </div>
                                    <form method="post">
                                        <input type="hidden" name="csrf_token" value="<?= e($csrf) ?>">
                                        <input type="hidden" name="action" value="update_category">
                                        <input type="hidden" name="id" value="<?= (int) $category['id'] ?>">
                                        <div class="admin-grid-3">
                                            <label class="admin-label">Name
                                                <input class="admin-input" type="text" name="name" value="<?= e((string) $category['name']) ?>" required>
                                            </label>
                                            <label class="admin-label">Slug
                                                <input class="admin-input" type="text" name="slug" value="<?= e((string) $category['slug']) ?>" required>
                                            </label>
                                            <label class="admin-label">Sort order
                                                <input class="admin-input" type="number" name="sort_order" value="<?= (int) $category['sort_order'] ?>">
                                            </label>
                                        </div>
                                        <label class="admin-label">Description
                                            <input class="admin-input" type="text" name="description" value="<?= e((string) $category['description']) ?>">
                                        </label>
                                        <label class="admin-label" style="display:inline-flex; align-items:center; gap:8px; margin-top:8px;">
                                            <input type="checkbox" name="is_active" value="1" <?= !empty($category['is_active']) ? 'checked' : '' ?>> Active on frontend
                                        </label>
                                        <div class="admin-actions">
                                            <button class="admin-btn" type="submit">Save</button>
                                        </div>
                                    </form>
                                    <form method="post" style="margin-top:6px;" onsubmit="return confirm('Delete this category and all attached blocks?');">
                                        <input type="hidden" name="csrf_token" value="<?= e($csrf) ?>">
                                        <input type="hidden" name="action" value="delete_category">
                                        <input type="hidden" name="id" value="<?= (int) $category['id'] ?>">
                                        <button class="admin-btn danger" type="submit">Delete category</button>
                                    </form>
                                </li>
                            <?php endforeach; ?>
                        </ul>
                    </section>

                    <section class="admin-panel" id="items">
                        <h2>Content Blocks</h2>
                        <form method="post">
                            <input type="hidden" name="csrf_token" value="<?= e($csrf) ?>">
                            <input type="hidden" name="action" value="add_item">
                            <div class="admin-grid-3">
                                <label class="admin-label">Category
                                    <select class="admin-select" name="category_id" required>
                                        <option value="">Select category</option>
                                        <?php foreach ($adminCategories as $category): ?>
                                            <option value="<?= (int) $category['id'] ?>"><?= e((string) $category['name']) ?></option>
                                        <?php endforeach; ?>
                                    </select>
                                </label>
                                <label class="admin-label">Title
                                    <input class="admin-input" type="text" name="title" required>
                                </label>
                                <label class="admin-label">Badge
                                    <input class="admin-input" type="text" name="badge" placeholder="Core, Planned, etc">
                                </label>
                            </div>
                            <label class="admin-label">Summary
                                <input class="admin-input" type="text" name="summary">
                            </label>
                            <label class="admin-label">Content
                                <textarea class="admin-textarea" name="content"></textarea>
                            </label>
                            <div class="admin-grid-3">
                                <label class="admin-label">CTA label
                                    <input class="admin-input" type="text" name="cta_label">
                                </label>
                                <label class="admin-label">CTA URL
                                    <input class="admin-input" type="url" name="cta_url">
                                </label>
                                <label class="admin-label">Sort order
                                    <input class="admin-input" type="number" name="sort_order" value="100">
                                </label>
                            </div>
                            <label class="admin-label" style="display:inline-flex; align-items:center; gap:8px; margin-top:8px;">
                                <input type="checkbox" name="is_active" value="1" checked> Active on frontend
                            </label>
                            <div class="admin-actions">
                                <button class="admin-btn" type="submit">Add block</button>
                            </div>
                        </form>

                        <ul class="admin-list" style="margin-top:12px;">
                            <?php foreach ($adminItems as $item): ?>
                                <li class="admin-list-item">
                                    <div class="admin-list-head">
                                        <strong><?= e((string) $item['title']) ?></strong>
                                        <span class="tag"><?= e((string) $item['category_name']) ?></span>
                                    </div>
                                    <form method="post">
                                        <input type="hidden" name="csrf_token" value="<?= e($csrf) ?>">
                                        <input type="hidden" name="action" value="update_item">
                                        <input type="hidden" name="id" value="<?= (int) $item['id'] ?>">
                                        <div class="admin-grid-3">
                                            <label class="admin-label">Category
                                                <select class="admin-select" name="category_id" required>
                                                    <?php foreach ($adminCategories as $category): ?>
                                                        <option value="<?= (int) $category['id'] ?>" <?= (int) $item['category_id'] === (int) $category['id'] ? 'selected' : '' ?>>
                                                            <?= e((string) $category['name']) ?>
                                                        </option>
                                                    <?php endforeach; ?>
                                                </select>
                                            </label>
                                            <label class="admin-label">Title
                                                <input class="admin-input" type="text" name="title" value="<?= e((string) $item['title']) ?>" required>
                                            </label>
                                            <label class="admin-label">Badge
                                                <input class="admin-input" type="text" name="badge" value="<?= e((string) $item['badge']) ?>">
                                            </label>
                                        </div>
                                        <label class="admin-label">Summary
                                            <input class="admin-input" type="text" name="summary" value="<?= e((string) $item['summary']) ?>">
                                        </label>
                                        <label class="admin-label">Content
                                            <textarea class="admin-textarea" name="content"><?= e((string) $item['content']) ?></textarea>
                                        </label>
                                        <div class="admin-grid-3">
                                            <label class="admin-label">CTA label
                                                <input class="admin-input" type="text" name="cta_label" value="<?= e((string) $item['cta_label']) ?>">
                                            </label>
                                            <label class="admin-label">CTA URL
                                                <input class="admin-input" type="url" name="cta_url" value="<?= e((string) $item['cta_url']) ?>">
                                            </label>
                                            <label class="admin-label">Sort order
                                                <input class="admin-input" type="number" name="sort_order" value="<?= (int) $item['sort_order'] ?>">
                                            </label>
                                        </div>
                                        <label class="admin-label" style="display:inline-flex; align-items:center; gap:8px; margin-top:8px;">
                                            <input type="checkbox" name="is_active" value="1" <?= !empty($item['is_active']) ? 'checked' : '' ?>> Active on frontend
                                        </label>
                                        <div class="admin-actions">
                                            <button class="admin-btn" type="submit">Save</button>
                                        </div>
                                    </form>
                                    <form method="post" style="margin-top:6px;" onsubmit="return confirm('Delete this content block?');">
                                        <input type="hidden" name="csrf_token" value="<?= e($csrf) ?>">
                                        <input type="hidden" name="action" value="delete_item">
                                        <input type="hidden" name="id" value="<?= (int) $item['id'] ?>">
                                        <button class="admin-btn danger" type="submit">Delete block</button>
                                    </form>
                                </li>
                            <?php endforeach; ?>
                        </ul>
                    </section>

                    <section class="admin-panel" id="messages">
                        <h2>Inbound Messages</h2>
                        <ul class="admin-list">
                            <?php if (count($adminMessages) === 0): ?>
                                <li class="admin-list-item">No messages yet.</li>
                            <?php else: ?>
                                <?php foreach ($adminMessages as $message): ?>
                                    <li class="admin-list-item">
                                        <div class="admin-list-head">
                                            <strong><?= e((string) $message['name']) ?> &lt;<?= e((string) $message['email']) ?>&gt;</strong>
                                            <span class="tag <?= !empty($message['is_read']) ? '' : 'unread' ?>">
                                                <?= !empty($message['is_read']) ? 'read' : 'unread' ?>
                                            </span>
                                        </div>
                                        <?php if ((string) $message['subject'] !== ''): ?>
                                            <p style="margin: 0 0 6px; color: #324969;"><strong>Subject:</strong> <?= e((string) $message['subject']) ?></p>
                                        <?php endif; ?>
                                        <p style="margin: 0 0 8px; color: #243552; white-space: pre-wrap;"><?= e((string) $message['message']) ?></p>
                                        <p style="margin: 0; color: #6c7d98; font-size: 0.85rem;"><?= e((string) $message['created_at']) ?></p>
                                        <div class="admin-actions">
                                            <?php if (!empty($message['is_read'])): ?>
                                                <form method="post">
                                                    <input type="hidden" name="csrf_token" value="<?= e($csrf) ?>">
                                                    <input type="hidden" name="action" value="mark_message_unread">
                                                    <input type="hidden" name="id" value="<?= (int) $message['id'] ?>">
                                                    <button class="admin-btn secondary" type="submit">Mark unread</button>
                                                </form>
                                            <?php else: ?>
                                                <form method="post">
                                                    <input type="hidden" name="csrf_token" value="<?= e($csrf) ?>">
                                                    <input type="hidden" name="action" value="mark_message_read">
                                                    <input type="hidden" name="id" value="<?= (int) $message['id'] ?>">
                                                    <button class="admin-btn" type="submit">Mark read</button>
                                                </form>
                                            <?php endif; ?>
                                            <form method="post" onsubmit="return confirm('Delete this message?');">
                                                <input type="hidden" name="csrf_token" value="<?= e($csrf) ?>">
                                                <input type="hidden" name="action" value="delete_message">
                                                <input type="hidden" name="id" value="<?= (int) $message['id'] ?>">
                                                <button class="admin-btn danger" type="submit">Delete</button>
                                            </form>
                                        </div>
                                    </li>
                                <?php endforeach; ?>
                            <?php endif; ?>
                        </ul>
                    </section>

                    <section class="admin-panel" id="security">
                        <h2>Security</h2>
                        <p style="margin-top:0; color:#5f7393;">Change backend login password.</p>
                        <form method="post">
                            <input type="hidden" name="csrf_token" value="<?= e($csrf) ?>">
                            <input type="hidden" name="action" value="change_password">
                            <div class="admin-grid-3">
                                <label class="admin-label">Current password
                                    <input class="admin-input" type="password" name="current_password" required>
                                </label>
                                <label class="admin-label">New password
                                    <input class="admin-input" type="password" name="new_password" minlength="12" required>
                                </label>
                                <label class="admin-label">Confirm new password
                                    <input class="admin-input" type="password" name="confirm_password" minlength="12" required>
                                </label>
                            </div>
                            <div class="admin-actions">
                                <button class="admin-btn" type="submit">Update password</button>
                            </div>
                        </form>
                    </section>
                </main>
            </div>
        </div>
    <?php endif; ?>
<?php endif; ?>
</body>
</html>
