/* GrayBar Meraki Manager – Web App Logic */

function app() {
  return {
    // ── Auth ──────────────────────────────────────────────────────────────────
    sessionId: localStorage.getItem('gmm_session'),
    apiKey: '',
    loginError: '',
    loginLoading: false,

    // ── Navigation ────────────────────────────────────────────────────────────
    page: 'dashboard',
    pageTitles: {
      dashboard: 'Dashboard', networks: 'Networks',
      exclusions: 'VPN Exclusions', copy: 'Copy Rules',
      compare: 'Compare Networks', newnet: 'New Network',
      activity: 'Activity Log',
    },

    // ── Org / Network state ───────────────────────────────────────────────────
    orgs: [],
    selectedOrgId: '',
    networks: [],
    networksLoading: false,

    // ── Dashboard ─────────────────────────────────────────────────────────────
    dashStats: { networkCount: 0, exclusionCount: 0, orgName: '' },
    dashLoading: false,

    // ── Networks page ─────────────────────────────────────────────────────────
    networkSearch: '',

    // ── Exclusions page ───────────────────────────────────────────────────────
    exclNetwork: null,
    exclCurrentRules: [],
    exclProposedRules: [],
    exclMode: 'merge',
    exclImportLoading: false,
    exclDryRunResult: null,
    exclDeployLoading: false,
    exclDeployResult: null,
    exclLoading: false,

    // ── Copy Wizard ───────────────────────────────────────────────────────────
    copyStep: 1,
    copySourceNetwork: null,
    copySourceRules: [],
    copySelectedRuleIdxs: [],
    copyDestNetworkIds: [],
    copyPreview: null,
    copyResults: null,
    copyLoading: false,

    // ── Compare ───────────────────────────────────────────────────────────────
    cmpSource: null,
    cmpTargetIds: [],
    cmpReport: null,
    cmpTab: 'vpn',
    cmpLoading: false,

    // ── New Network Wizard ────────────────────────────────────────────────────
    nnStep: 1,
    nnTemplate: null,
    nnCloneConfig: null,
    nnName: '',
    nnTimezone: 'America/Los_Angeles',
    nnNotes: '',
    nnCopyTags: true,
    nnCopyVpn: true,
    nnCopyRoutes: false,
    nnCopyL3: false,
    nnCopyL7: false,
    nnCopySSIDs: false,
    nnCopySettings: false,
    nnSsidPsks: {},
    nnResult: null,
    nnLoading: false,

    // ── Activity Log ──────────────────────────────────────────────────────────
    actLog: [],

    // =========================================================================
    // Init
    // =========================================================================
    async init() {
      if (this.sessionId) {
        try {
          this.orgs = await this.api('GET', '/api/orgs');
          if (this.orgs.length) {
            this.selectedOrgId = this.orgs[0].id;
            await this.loadNetworks();
          }
        } catch {
          this.sessionId = null;
          localStorage.removeItem('gmm_session');
        }
      }
    },

    // =========================================================================
    // Auth
    // =========================================================================
    async login() {
      this.loginError = '';
      this.loginLoading = true;
      try {
        const res = await this.api('POST', '/api/login', { api_key: this.apiKey });
        this.sessionId = res.session_id;
        localStorage.setItem('gmm_session', res.session_id);
        this.orgs = res.orgs;
        if (this.orgs.length) {
          this.selectedOrgId = this.orgs[0].id;
          await this.loadNetworks();
          await this.loadDashboard();
        }
        this.log('Logged in successfully.', 'success');
      } catch (e) {
        this.loginError = e.message;
      } finally {
        this.loginLoading = false;
      }
    },

    async logout() {
      await this.api('POST', '/api/logout').catch(() => {});
      this.sessionId = null;
      localStorage.removeItem('gmm_session');
      this.orgs = []; this.networks = []; this.page = 'dashboard';
    },

    // =========================================================================
    // Networks / Orgs
    // =========================================================================
    async loadNetworks() {
      if (!this.selectedOrgId) return;
      this.networksLoading = true;
      try {
        this.networks = await this.api('GET', `/api/networks?org_id=${this.selectedOrgId}`);
        this.log(`Loaded ${this.networks.length} network(s).`, 'info');
      } catch (e) {
        this.log(`Load networks failed: ${e.message}`, 'error');
      } finally {
        this.networksLoading = false;
      }
    },

    async onOrgChange() {
      this.networks = [];
      await this.loadNetworks();
      await this.loadDashboard();
    },

    get filteredNetworks() {
      const q = this.networkSearch.toLowerCase();
      return this.networks.filter(n =>
        !q || n.name.toLowerCase().includes(q) || (n.tags || []).join(' ').toLowerCase().includes(q)
      );
    },

    selectedOrg() {
      return this.orgs.find(o => o.id === this.selectedOrgId) || null;
    },

    // =========================================================================
    // Dashboard
    // =========================================================================
    async loadDashboard() {
      this.dashLoading = true;
      this.dashStats = { networkCount: this.networks.length, exclusionCount: '…', orgName: this.selectedOrg()?.name || '' };
      try {
        let total = 0;
        await Promise.all(this.networks.map(async n => {
          try {
            const rs = await this.api('GET', `/api/exclusions?org_id=${this.selectedOrgId}&network_id=${n.id}`);
            total += rs.rules.length;
          } catch {}
        }));
        this.dashStats.exclusionCount = total;
      } finally {
        this.dashLoading = false;
      }
    },

    // =========================================================================
    // VPN Exclusions
    // =========================================================================
    async loadExclusions(network) {
      this.exclNetwork = network;
      this.exclCurrentRules = [];
      this.exclProposedRules = [];
      this.exclDryRunResult = null;
      this.exclDeployResult = null;
      this.exclLoading = true;
      this.page = 'exclusions';
      try {
        const rs = await this.api('GET', `/api/exclusions?org_id=${this.selectedOrgId}&network_id=${network.id}`);
        this.exclCurrentRules = rs.rules;
        this.log(`Loaded ${rs.rules.length} VPN rule(s) for ${network.name}.`, 'info');
      } catch (e) {
        this.log(`Failed to load rules: ${e.message}`, 'error');
      } finally {
        this.exclLoading = false;
      }
    },

    async importFile(event) {
      const file = event.target.files[0];
      if (!file) return;
      this.exclImportLoading = true;
      try {
        const fd = new FormData();
        fd.append('file', file);
        const rs = await this.apiForm('/api/exclusions/import', fd);
        this.exclProposedRules = rs.rules;
        this.exclMode = rs.mode || 'merge';
        this.exclDryRunResult = null;
        this.log(`Imported ${rs.rules.length} rule(s) from ${file.name}.`, 'success');
      } catch (e) {
        this.log(`Import failed: ${e.message}`, 'error');
      } finally {
        this.exclImportLoading = false;
        event.target.value = '';
      }
    },

    async runDryRun() {
      if (!this.exclNetwork || !this.exclProposedRules.length) return;
      this.exclLoading = true;
      this.exclDryRunResult = null;
      try {
        this.exclDryRunResult = await this.api('POST', '/api/exclusions/dry-run', {
          org_id: this.selectedOrgId,
          network_id: this.exclNetwork.id,
          network_name: this.exclNetwork.name,
          proposed_rules: this.exclProposedRules,
          mode: this.exclMode,
        });
        this.log(`Dry run: ${this.exclDryRunResult.change_count} change(s) for ${this.exclNetwork.name}.`, 'info');
      } catch (e) {
        this.log(`Dry run failed: ${e.message}`, 'error');
      } finally {
        this.exclLoading = false;
      }
    },

    async deployRules() {
      if (!this.exclDryRunResult || this.exclDryRunResult.has_blockers) return;
      if (!confirm(`Deploy ${this.exclDryRunResult.change_count} change(s) to ${this.exclNetwork.name}?`)) return;
      this.exclDeployLoading = true;
      this.exclDeployResult = null;
      try {
        await this.api('POST', '/api/exclusions/deploy', { network_id: this.exclNetwork.id });
        this.exclDeployResult = { ok: true };
        this.log(`Deployed successfully to ${this.exclNetwork.name}.`, 'success');
        this.exclDryRunResult = null;
        await this.loadExclusions(this.exclNetwork);
      } catch (e) {
        this.exclDeployResult = { ok: false, error: e.message };
        this.log(`Deploy failed: ${e.message}`, 'error');
      } finally {
        this.exclDeployLoading = false;
      }
    },

    changeClass(kind) {
      return { new: 'change-new', removed: 'change-removed', unchanged: 'change-unchanged', duplicate: 'change-duplicate', invalid: 'change-invalid' }[kind] || '';
    },

    changeIcon(kind) {
      return { new: '＋', removed: '−', unchanged: '=', duplicate: '⚠', invalid: '✗' }[kind] || '?';
    },

    // =========================================================================
    // Copy Wizard
    // =========================================================================
    startCopyWizard() {
      this.copyStep = 1; this.copySourceNetwork = null; this.copySourceRules = [];
      this.copySelectedRuleIdxs = []; this.copyDestNetworkIds = [];
      this.copyPreview = null; this.copyResults = null;
      this.page = 'copy';
    },

    async copySelectSource(network) {
      this.copySourceNetwork = network;
      this.copyLoading = true;
      try {
        const rs = await this.api('GET', `/api/exclusions?org_id=${this.selectedOrgId}&network_id=${network.id}`);
        this.copySourceRules = rs.rules;
        this.copySelectedRuleIdxs = rs.rules.map((_, i) => i);
        this.copyStep = 2;
      } catch (e) {
        this.log(`Failed to load rules: ${e.message}`, 'error');
      } finally {
        this.copyLoading = false;
      }
    },

    toggleCopyRule(i) {
      const idx = this.copySelectedRuleIdxs.indexOf(i);
      if (idx >= 0) this.copySelectedRuleIdxs.splice(idx, 1);
      else this.copySelectedRuleIdxs.push(i);
    },

    toggleCopyDest(id) {
      const idx = this.copyDestNetworkIds.indexOf(id);
      if (idx >= 0) this.copyDestNetworkIds.splice(idx, 1);
      else this.copyDestNetworkIds.push(id);
    },

    get copySelectedRules() {
      return this.copySelectedRuleIdxs.map(i => this.copySourceRules[i]).filter(Boolean);
    },

    get copyDestNetworks() {
      return this.networks.filter(n => this.copyDestNetworkIds.includes(n.id) && n.id !== this.copySourceNetwork?.id);
    },

    async runCopyPreview() {
      if (!this.copySelectedRules.length || !this.copyDestNetworks.length) return;
      this.copyLoading = true;
      try {
        this.copyPreview = await this.api('POST', '/api/copy/preview', {
          org_id: this.selectedOrgId,
          selected_rules: this.copySelectedRules,
          destination_networks: this.copyDestNetworks,
        });
        this.copyStep = 4;
      } catch (e) {
        this.log(`Preview failed: ${e.message}`, 'error');
      } finally {
        this.copyLoading = false;
      }
    },

    async runCopyExecute() {
      if (!confirm(`Copy ${this.copySelectedRules.length} rule(s) to ${this.copyDestNetworks.length} network(s)?`)) return;
      this.copyLoading = true;
      try {
        this.copyResults = await this.api('POST', '/api/copy/execute', {
          org_id: this.selectedOrgId,
          selected_rules: this.copySelectedRules,
          destination_networks: this.copyDestNetworks,
        });
        this.copyStep = 5;
        const added = this.copyResults.reduce((s, r) => s + r.rules_added, 0);
        this.log(`Copy complete: ${added} rule(s) added across ${this.copyResults.length} network(s).`, 'success');
      } catch (e) {
        this.log(`Copy failed: ${e.message}`, 'error');
      } finally {
        this.copyLoading = false;
      }
    },

    ruleLabel(rule) {
      if (rule.destination) return `${rule.protocol} → ${rule.destination}:${rule.port}`;
      if (rule.name) return rule.name;
      if (rule.application_id) return rule.application_id;
      return '—';
    },

    // =========================================================================
    // Compare Networks
    // =========================================================================
    startCompare() {
      this.cmpSource = null; this.cmpTargetIds = []; this.cmpReport = null; this.cmpTab = 'vpn';
      this.page = 'compare';
    },

    toggleCmpTarget(id) {
      const idx = this.cmpTargetIds.indexOf(id);
      if (idx >= 0) this.cmpTargetIds.splice(idx, 1);
      else this.cmpTargetIds.push(id);
    },

    get cmpTargetNetworks() {
      return this.networks.filter(n => this.cmpTargetIds.includes(n.id) && n.id !== this.cmpSource?.id);
    },

    async runCompare() {
      if (!this.cmpSource || !this.cmpTargetNetworks.length) return;
      this.cmpLoading = true; this.cmpReport = null;
      try {
        this.cmpReport = await this.api('POST', '/api/compare', {
          org_id: this.selectedOrgId,
          source_network: this.cmpSource,
          target_networks: this.cmpTargetNetworks,
        });
        this.log(`Compare complete: ${this.cmpReport.vpn_rules.length} VPN rule(s) compared.`, 'info');
      } catch (e) {
        this.log(`Compare failed: ${e.message}`, 'error');
      } finally {
        this.cmpLoading = false;
      }
    },

    cellClass(cell) {
      return { match: 'compare-match', missing: 'compare-missing', different: 'compare-different', na: 'compare-na' }[cell?.status] || '';
    },

    cellIcon(cell) {
      return { match: '✓', missing: '−', different: '≠', na: 'n/a' }[cell?.status] || '?';
    },

    // =========================================================================
    // New Network Wizard
    // =========================================================================
    startNewNet() {
      this.nnStep = 1; this.nnTemplate = null; this.nnCloneConfig = null;
      this.nnName = ''; this.nnNotes = ''; this.nnSsidPsks = {};
      this.nnCopyTags = true; this.nnCopyVpn = true; this.nnCopyRoutes = false;
      this.nnCopyL3 = false; this.nnCopyL7 = false; this.nnCopySSIDs = false; this.nnCopySettings = false;
      this.nnResult = null;
      this.page = 'newnet';
    },

    async nnSelectTemplate(network) {
      this.nnTemplate = network;
      this.nnLoading = true;
      this.nnTimezone = 'America/Los_Angeles';
      try {
        this.nnCloneConfig = await this.api('POST', '/api/network/clone-config', {
          org_id: this.selectedOrgId,
          source_network: network,
        });
        this.nnTimezone = this.nnCloneConfig.source_timezone || 'America/Los_Angeles';
        this.nnStep = 2;
      } catch (e) {
        this.log(`Failed to read template: ${e.message}`, 'error');
      } finally {
        this.nnLoading = false;
      }
    },

    get nnPskSsids() {
      if (!this.nnCloneConfig || !this.nnCopySSIDs) return [];
      return (this.nnCloneConfig.ssids || []).filter(s => s.authMode === 'psk' && s.enabled);
    },

    async nnCreate() {
      if (!this.nnName.trim()) { alert('Enter a network name.'); return; }
      if (!confirm(`Create network "${this.nnName}"?`)) return;
      this.nnLoading = true; this.nnResult = null;
      try {
        this.nnResult = await this.api('POST', '/api/network/create', {
          org_id: this.selectedOrgId,
          source_network_id: this.nnTemplate.id,
          name: this.nnName,
          timezone: this.nnTimezone,
          notes: this.nnNotes,
          copy_tags: this.nnCopyTags,
          copy_vpn_exclusions: this.nnCopyVpn,
          copy_static_routes: this.nnCopyRoutes,
          copy_l3_firewall: this.nnCopyL3,
          copy_l7_firewall: this.nnCopyL7,
          copy_ssids: this.nnCopySSIDs,
          copy_network_settings: this.nnCopySettings,
          ssid_psks: this.nnSsidPsks,
        });
        this.nnStep = 6;
        if (this.nnResult.success) {
          this.log(`Network "${this.nnResult.network_name}" created successfully.`, 'success');
          await this.loadNetworks();
        } else {
          this.log(`Network creation failed: ${this.nnResult.error}`, 'error');
        }
      } catch (e) {
        this.log(`Create failed: ${e.message}`, 'error');
      } finally {
        this.nnLoading = false;
      }
    },

    // =========================================================================
    // Activity Log
    // =========================================================================
    log(msg, level = 'info') {
      const time = new Date().toLocaleTimeString();
      this.actLog.unshift({ time, msg, level });
      if (this.actLog.length > 200) this.actLog.pop();
    },

    // =========================================================================
    // API helpers
    // =========================================================================
    async api(method, path, body) {
      const opts = {
        method,
        headers: { 'X-Session-ID': this.sessionId || '' },
      };
      if (body) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
      }
      const res = await fetch(path, opts);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'Request failed');
      }
      return res.json();
    },

    async apiForm(path, formData) {
      const res = await fetch(path, {
        method: 'POST',
        headers: { 'X-Session-ID': this.sessionId || '' },
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'Upload failed');
      }
      return res.json();
    },

    navigate(p) { this.page = p; },
  };
}
