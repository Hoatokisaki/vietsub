using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Net;
using System.Text;
using System.Text.RegularExpressions;
using System.Windows.Forms;

namespace LuaVietsupPremiumManager
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
            Application.Run(new MainForm());
        }
    }

    public class MainForm : Form
    {
        private TextBox txtUrl;
        private TextBox txtKey;
        private TextBox txtEmail;
        private TextBox txtPassword;
        private Button btnLogin;
        private Label lblStatus;

        private TextBox txtHwid;
        private TextBox txtLabel;
        private TextBox txtDays;
        private Button btnGrant;

        private ListView lvLicenses;
        private Button btnRefresh;
        private Button btnRevoke;

        private string accessToken = "";
        private string configPath = "";

        public MainForm()
        {
            InitializeComponent();
            LoadConfig();
        }

        private void InitializeComponent()
        {
            this.Text = "luaVietsup — Quản lý Premium từ xa (Chủ Ứng Dụng)";
            this.Size = new Size(960, 720);
            this.MinimumSize = new Size(850, 600);
            this.StartPosition = FormStartPosition.CenterScreen;
            this.BackColor = Color.FromArgb(16, 24, 39); // #101827
            this.ForeColor = Color.FromArgb(229, 237, 247);
            this.Font = new Font("Segoe UI", 9.5f);

            try
            {
                string iconPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, @"source\assets\luaVietsup\icon.ico");
                if (!File.Exists(iconPath))
                    iconPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, @"_internal\icon.ico");
                if (File.Exists(iconPath))
                    this.Icon = new Icon(iconPath);
            }
            catch { }

            var pnlMain = new Panel { Dock = DockStyle.Fill, AutoScroll = true, Padding = new Padding(18) };
            this.Controls.Add(pnlMain);

            int y = 10;

            // Title
            var lblTitle = new Label
            {
                Text = "Quản lý HWID Premium Từ Xa (Chủ Ứng Dụng)",
                Font = new Font("Segoe UI", 16f, FontStyle.Bold),
                ForeColor = Color.FromArgb(96, 165, 250), // #60a5fa
                Location = new Point(15, y),
                AutoSize = true
            };
            pnlMain.Controls.Add(lblTitle);
            y += 35;

            var lblSubtitle = new Label
            {
                Text = "Công cụ độc lập dành riêng cho admin để cấp, gia hạn hoặc thu hồi quyền Premium qua máy chủ Supabase.",
                ForeColor = Color.FromArgb(156, 163, 175),
                Location = new Point(16, y),
                AutoSize = true
            };
            pnlMain.Controls.Add(lblSubtitle);
            y += 30;

            // Group 1: Kết nối Supabase
            var grpConn = CreateGroupBox("Cấu hình kết nối Supabase", 15, y, 910, 85);
            pnlMain.Controls.Add(grpConn);

            var lblUrl = CreateLabel("Project URL:", 15, 25);
            grpConn.Controls.Add(lblUrl);
            txtUrl = CreateTextBox(115, 22, 360, "https://tquusprgcvyptgnvftwz.supabase.co");
            grpConn.Controls.Add(txtUrl);

            var lblKey = CreateLabel("Publishable Key:", 490, 25);
            grpConn.Controls.Add(lblKey);
            txtKey = CreateTextBox(610, 22, 280, "sb_publishable__vJ7EhUYTxazPZGpY2ZW2A_Cd8fqZjo");
            txtKey.UseSystemPasswordChar = true;
            grpConn.Controls.Add(txtKey);

            var btnShowKey = new Button
            {
                Text = "👁",
                Location = new Point(865, 50),
                Size = new Size(30, 25),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(37, 99, 235),
                ForeColor = Color.White
            };
            btnShowKey.Click += (s, e) => { txtKey.UseSystemPasswordChar = !txtKey.UseSystemPasswordChar; };
            grpConn.Controls.Add(btnShowKey);

            y += 95;

            // Group 2: Đăng nhập Admin
            var grpLogin = CreateGroupBox("Đăng nhập tài khoản Quản trị viên (Supabase Auth)", 15, y, 910, 75);
            pnlMain.Controls.Add(grpLogin);

            grpLogin.Controls.Add(CreateLabel("Email Admin:", 15, 28));
            txtEmail = CreateTextBox(115, 25, 280, "");
            grpLogin.Controls.Add(txtEmail);

            grpLogin.Controls.Add(CreateLabel("Mật khẩu:", 415, 28));
            txtPassword = CreateTextBox(490, 25, 220, "");
            txtPassword.UseSystemPasswordChar = true;
            grpLogin.Controls.Add(txtPassword);

            btnLogin = CreateButton("Đăng nhập", 730, 23, 160, 30, Color.FromArgb(37, 99, 235));
            btnLogin.Click += BtnLogin_Click;
            grpLogin.Controls.Add(btnLogin);

            y += 85;

            // Status label
            lblStatus = new Label
            {
                Text = "Chưa đăng nhập. Hãy nhập Email/Mật khẩu quản trị và bấm Đăng nhập.",
                ForeColor = Color.FromArgb(245, 158, 11), // Orange/Amber
                Location = new Point(18, y),
                AutoSize = true,
                Font = new Font("Segoe UI", 9.5f, FontStyle.Italic)
            };
            pnlMain.Controls.Add(lblStatus);
            y += 28;

            // Group 3: Cấp / Gia hạn Premium
            var grpGrant = CreateGroupBox("Cấp / Gia hạn quyền Premium cho HWID", 15, y, 910, 95);
            pnlMain.Controls.Add(grpGrant);

            grpGrant.Controls.Add(CreateLabel("HWID thiết bị:", 15, 25));
            txtHwid = CreateTextBox(115, 22, 420, "");
            grpGrant.Controls.Add(txtHwid);

            grpGrant.Controls.Add(CreateLabel("Số ngày:", 555, 25));
            txtDays = CreateTextBox(625, 22, 70, "0");
            grpGrant.Controls.Add(txtDays);

            var lblDaysHint = new Label
            {
                Text = "(0 = Vĩnh viễn)",
                ForeColor = Color.FromArgb(156, 163, 175),
                Location = new Point(705, 25),
                AutoSize = true
            };
            grpGrant.Controls.Add(lblDaysHint);

            grpGrant.Controls.Add(CreateLabel("Tên / Ghi chú:", 15, 58));
            txtLabel = CreateTextBox(115, 55, 420, "");
            grpGrant.Controls.Add(txtLabel);

            btnGrant = CreateButton("Cấp / Gia hạn Premium", 555, 53, 200, 30, Color.FromArgb(16, 185, 129)); // Green
            btnGrant.Click += BtnGrant_Click;
            grpGrant.Controls.Add(btnGrant);

            y += 105;

            // Group 4: Danh sách HWID đã cấp
            var lblListTitle = new Label
            {
                Text = "Danh sách thiết bị đã cấp quyền trên Server:",
                Font = new Font("Segoe UI", 10.5f, FontStyle.Bold),
                ForeColor = Color.FromArgb(229, 237, 247),
                Location = new Point(16, y),
                AutoSize = true
            };
            pnlMain.Controls.Add(lblListTitle);

            btnRefresh = CreateButton("Làm mới danh sách", 640, y - 5, 130, 28, Color.FromArgb(55, 65, 81));
            btnRefresh.Click += (s, e) => RefreshLicenses();
            pnlMain.Controls.Add(btnRefresh);

            btnRevoke = CreateButton("Thu hồi HWID đã chọn", 780, y - 5, 145, 28, Color.FromArgb(220, 38, 38)); // Red
            btnRevoke.Click += BtnRevoke_Click;
            pnlMain.Controls.Add(btnRevoke);

            y += 32;

            lvLicenses = new ListView
            {
                Location = new Point(15, y),
                Size = new Size(910, 230),
                View = View.Details,
                FullRowSelect = true,
                GridLines = true,
                BackColor = Color.FromArgb(11, 18, 32),
                ForeColor = Color.FromArgb(229, 237, 247),
                Font = new Font("Consolas", 9.5f)
            };
            lvLicenses.Columns.Add("HWID Cuối", 130);
            lvLicenses.Columns.Add("Người dùng / Ghi chú", 260);
            lvLicenses.Columns.Add("Trạng thái", 140);
            lvLicenses.Columns.Add("Hết hạn", 170);
            lvLicenses.Columns.Add("Mã nhận diện (SHA256)", 200);
            pnlMain.Controls.Add(lvLicenses);
        }

        private GroupBox CreateGroupBox(string text, int x, int y, int w, int h)
        {
            return new GroupBox
            {
                Text = text,
                Location = new Point(x, y),
                Size = new Size(w, h),
                ForeColor = Color.FromArgb(96, 165, 250),
                BackColor = Color.FromArgb(23, 35, 55),
                Font = new Font("Segoe UI", 9.5f, FontStyle.Bold)
            };
        }

        private Label CreateLabel(string text, int x, int y)
        {
            return new Label
            {
                Text = text,
                Location = new Point(x, y),
                AutoSize = true,
                ForeColor = Color.FromArgb(229, 237, 247),
                Font = new Font("Segoe UI", 9.5f, FontStyle.Regular)
            };
        }

        private TextBox CreateTextBox(int x, int y, int w, string defaultVal)
        {
            return new TextBox
            {
                Location = new Point(x, y),
                Size = new Size(w, 24),
                Text = defaultVal,
                BackColor = Color.FromArgb(11, 18, 32),
                ForeColor = Color.FromArgb(229, 237, 247),
                BorderStyle = BorderStyle.FixedSingle,
                Font = new Font("Segoe UI", 9.5f, FontStyle.Regular)
            };
        }

        private Button CreateButton(string text, int x, int y, int w, int h, Color bg)
        {
            var btn = new Button
            {
                Text = text,
                Location = new Point(x, y),
                Size = new Size(w, h),
                BackColor = bg,
                ForeColor = Color.White,
                FlatStyle = FlatStyle.Flat,
                Cursor = Cursors.Hand,
                Font = new Font("Segoe UI", 9.5f, FontStyle.Bold)
            };
            btn.FlatAppearance.BorderSize = 0;
            return btn;
        }

        private void LoadConfig()
        {
            try
            {
                string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
                configPath = Path.Combine(appData, @"luaVietsup\license_service_config.json");
                if (!File.Exists(configPath))
                {
                    string local = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, @"_internal\license_service_config.json");
                    if (File.Exists(local)) configPath = local;
                }

                if (File.Exists(configPath))
                {
                    string json = File.ReadAllText(configPath);
                    var matchUrl = Regex.Match(json, @"""url""\s*:\s*""([^""]+)""");
                    var matchKey = Regex.Match(json, @"""publishable_key""\s*:\s*""([^""]+)""");
                    if (matchUrl.Success) txtUrl.Text = matchUrl.Groups[1].Value;
                    if (matchKey.Success) txtKey.Text = matchKey.Groups[1].Value;
                }
            }
            catch { }
        }

        private void SaveConfig()
        {
            try
            {
                string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
                string dir = Path.Combine(appData, "luaVietsup");
                Directory.CreateDirectory(dir);
                string path = Path.Combine(dir, "license_service_config.json");
                string json = string.Format("{{\n  \"url\": \"{0}\",\n  \"publishable_key\": \"{1}\"\n}}", txtUrl.Text.Trim().TrimEnd('/'), txtKey.Text.Trim());
                File.WriteAllText(path, json, Encoding.UTF8);

                string local = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, @"_internal\license_service_config.json");
                if (File.Exists(local)) File.WriteAllText(local, json, Encoding.UTF8);
            }
            catch { }
        }

        private string HttpPostJson(string url, string jsonBody, Dictionary<string, string> headers)
        {
            var req = (HttpWebRequest)WebRequest.Create(url);
            req.Method = "POST";
            req.ContentType = "application/json";
            req.Timeout = 15000;

            if (headers != null)
            {
                foreach (var kv in headers)
                {
                    if (kv.Key.Equals("Authorization", StringComparison.OrdinalIgnoreCase))
                        req.Headers[HttpRequestHeader.Authorization] = kv.Value;
                    else
                        req.Headers[kv.Key] = kv.Value;
                }
            }

            if (!string.IsNullOrEmpty(jsonBody))
            {
                byte[] data = Encoding.UTF8.GetBytes(jsonBody);
                req.ContentLength = data.Length;
                using (var stream = req.GetRequestStream())
                {
                    stream.Write(data, 0, data.Length);
                }
            }

            try
            {
                using (var res = (HttpWebResponse)req.GetResponse())
                using (var reader = new StreamReader(res.GetResponseStream(), Encoding.UTF8))
                {
                    return reader.ReadToEnd();
                }
            }
            catch (WebException wex)
            {
                if (wex.Response != null)
                {
                    using (var reader = new StreamReader(wex.Response.GetResponseStream(), Encoding.UTF8))
                    {
                        string err = reader.ReadToEnd();
                        throw new Exception(err);
                    }
                }
                throw;
            }
        }

        private void BtnLogin_Click(object sender, EventArgs e)
        {
            string url = txtUrl.Text.Trim().TrimEnd('/');
            string key = txtKey.Text.Trim();
            string email = txtEmail.Text.Trim();
            string password = txtPassword.Text;

            if (string.IsNullOrEmpty(url) || string.IsNullOrEmpty(key))
            {
                MessageBox.Show("Vui lòng nhập Project URL và Publishable Key.", "Thiếu thông tin", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            if (string.IsNullOrEmpty(email) || string.IsNullOrEmpty(password))
            {
                MessageBox.Show("Vui lòng nhập Email và Mật khẩu Supabase Auth.", "Thiếu thông tin", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            try
            {
                lblStatus.Text = "Đang kết nối và xác thực tài khoản...";
                lblStatus.ForeColor = Color.FromArgb(96, 165, 250);
                this.Cursor = Cursors.WaitCursor;

                SaveConfig();

                string authUrl = url + "/auth/v1/token?grant_type=password";
                string body = string.Format("{{\"email\":\"{0}\",\"password\":\"{1}\"}}", email.Replace("\"", "\\\""), password.Replace("\"", "\\\""));
                var headers = new Dictionary<string, string> { { "apikey", key } };

                string res = HttpPostJson(authUrl, body, headers);
                var match = Regex.Match(res, @"""access_token""\s*:\s*""([^""]+)""");
                if (!match.Success)
                {
                    throw new Exception("Máy chủ không trả về access_token: " + res);
                }

                accessToken = match.Groups[1].Value;
                lblStatus.Text = "Đăng nhập thành công! Đang tải danh sách bản quyền...";
                lblStatus.ForeColor = Color.FromArgb(52, 211, 153); // Light green

                RefreshLicenses();
            }
            catch (Exception ex)
            {
                lblStatus.Text = "Đăng nhập thất bại: " + ex.Message;
                lblStatus.ForeColor = Color.FromArgb(239, 68, 68); // Red
                MessageBox.Show("Lỗi đăng nhập: " + ex.Message, "Đăng nhập thất bại", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                this.Cursor = Cursors.Default;
            }
        }

        private void RefreshLicenses()
        {
            if (string.IsNullOrEmpty(accessToken))
            {
                MessageBox.Show("Vui lòng đăng nhập tài khoản Quản trị trước.", "Chưa đăng nhập", MessageBoxButtons.OK, MessageBoxIcon.Information);
                return;
            }

            try
            {
                this.Cursor = Cursors.WaitCursor;
                string url = txtUrl.Text.Trim().TrimEnd('/') + "/functions/v1/license-admin";
                string key = txtKey.Text.Trim();
                var headers = new Dictionary<string, string>
                {
                    { "apikey", key },
                    { "Authorization", "Bearer " + accessToken }
                };

                string res = HttpPostJson(url, "{\"action\":\"list\"}", headers);

                lvLicenses.Items.Clear();

                // Simple JSON array extraction for licenses
                var itemMatches = Regex.Matches(res, @"\{[^{}]*""hwid_sha256""[^{}]*\}");
                foreach (Match m in itemMatches)
                {
                    string itemJson = m.Value;
                    string hint = ExtractJsonString(itemJson, "hwid_hint");
                    string holder = ExtractJsonString(itemJson, "holder_name");
                    string expires = ExtractJsonString(itemJson, "expires_at");
                    string hash = ExtractJsonString(itemJson, "hwid_sha256");
                    bool active = itemJson.Contains("\"active\":true") || itemJson.Contains("\"active\": true");

                    if (string.IsNullOrEmpty(expires))
                        expires = "Vĩnh viễn";
                    else
                        expires = expires.Replace("T", " ").Substring(0, Math.Min(16, expires.Length));

                    string status = active ? "Đang hoạt động" : "Đã thu hồi";

                    var lvi = new ListViewItem(hint);
                    lvi.SubItems.Add(holder);
                    lvi.SubItems.Add(status);
                    lvi.SubItems.Add(expires);
                    lvi.SubItems.Add(hash);
                    lvi.Tag = hash;

                    if (!active)
                    {
                        lvi.ForeColor = Color.FromArgb(156, 163, 175);
                    }
                    else
                    {
                        lvi.ForeColor = Color.FromArgb(52, 211, 153);
                    }

                    lvLicenses.Items.Add(lvi);
                }

                lblStatus.Text = string.Format("Đã tải {0} bản quyền thiết bị từ máy chủ.", lvLicenses.Items.Count);
                lblStatus.ForeColor = Color.FromArgb(52, 211, 153);
            }
            catch (Exception ex)
            {
                lblStatus.Text = "Lỗi khi tải danh sách: " + ex.Message;
                lblStatus.ForeColor = Color.FromArgb(239, 68, 68);
                MessageBox.Show("Lỗi tải danh sách: " + ex.Message, "Lỗi kết nối", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                this.Cursor = Cursors.Default;
            }
        }

        private string ExtractJsonString(string json, string key)
        {
            var m = Regex.Match(json, "\"" + key + @"\""\s*:\s*\""([^\""]*)\""");
            return m.Success ? m.Groups[1].Value : "";
        }

        private void BtnGrant_Click(object sender, EventArgs e)
        {
            if (string.IsNullOrEmpty(accessToken))
            {
                MessageBox.Show("Vui lòng đăng nhập trước khi cấp bản quyền.", "Chưa đăng nhập", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string rawHwid = txtHwid.Text.Trim();
            if (string.IsNullOrEmpty(rawHwid))
            {
                MessageBox.Show("Vui lòng nhập HWID của thiết bị (lấy từ trang Cài đặt -> Tài khoản).", "Thiếu HWID", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            int days = 0;
            int.TryParse(txtDays.Text.Trim(), out days);

            string label = txtLabel.Text.Trim();

            try
            {
                this.Cursor = Cursors.WaitCursor;
                string url = txtUrl.Text.Trim().TrimEnd('/') + "/functions/v1/license-admin";
                string key = txtKey.Text.Trim();
                var headers = new Dictionary<string, string>
                {
                    { "apikey", key },
                    { "Authorization", "Bearer " + accessToken }
                };

                string body = string.Format(
                    "{{\"action\":\"grant\",\"hwid\":\"{0}\",\"label\":\"{1}\",\"expiry_days\":{2}}}",
                    rawHwid.Replace("\"", "\\\""),
                    label.Replace("\"", "\\\""),
                    days
                );

                string res = HttpPostJson(url, body, headers);
                MessageBox.Show("Cấp quyền Premium thành công cho HWID!\nThiết bị sẽ nhận bản quyền ngay khi mở app.", "Thành công", MessageBoxButtons.OK, MessageBoxIcon.Information);
                txtHwid.Text = "";
                RefreshLicenses();
            }
            catch (Exception ex)
            {
                MessageBox.Show("Lỗi cấp Premium: " + ex.Message, "Không thể cấp", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                this.Cursor = Cursors.Default;
            }
        }

        private void BtnRevoke_Click(object sender, EventArgs e)
        {
            if (string.IsNullOrEmpty(accessToken))
            {
                MessageBox.Show("Vui lòng đăng nhập trước khi thu hồi.", "Chưa đăng nhập", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            if (lvLicenses.SelectedItems.Count == 0)
            {
                MessageBox.Show("Vui lòng chọn 1 thiết bị trong danh sách bên dưới để thu hồi.", "Chưa chọn dòng", MessageBoxButtons.OK, MessageBoxIcon.Information);
                return;
            }

            string hash = lvLicenses.SelectedItems[0].Tag as string;
            string holder = lvLicenses.SelectedItems[0].SubItems[1].Text;

            var confirm = MessageBox.Show(
                string.Format("Bạn có chắc chắn muốn thu hồi Premium của thiết bị '{0}' ({1}) không?\nSau khi thu hồi, thiết bị sẽ trở về trạng thái hết hạn.", holder, hash.Substring(0, Math.Min(16, hash.Length))),
                "Xác nhận thu hồi",
                MessageBoxButtons.YesNo,
                MessageBoxIcon.Question
            );

            if (confirm != DialogResult.Yes) return;

            try
            {
                this.Cursor = Cursors.WaitCursor;
                string url = txtUrl.Text.Trim().TrimEnd('/') + "/functions/v1/license-admin";
                string key = txtKey.Text.Trim();
                var headers = new Dictionary<string, string>
                {
                    { "apikey", key },
                    { "Authorization", "Bearer " + accessToken }
                };

                string body = string.Format("{{\"action\":\"revoke\",\"hwid_sha256\":\"{0}\"}}", hash);
                HttpPostJson(url, body, headers);

                MessageBox.Show("Đã thu hồi bản quyền thành công!", "Đã thu hồi", MessageBoxButtons.OK, MessageBoxIcon.Information);
                RefreshLicenses();
            }
            catch (Exception ex)
            {
                MessageBox.Show("Lỗi thu hồi Premium: " + ex.Message, "Không thể thu hồi", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                this.Cursor = Cursors.Default;
            }
        }
    }
}
