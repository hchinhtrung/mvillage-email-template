# M Village Email Templates

A comprehensive collection of HTML email templates for M Village hotel services, supporting both English and Vietnamese languages across various customer touchpoints.

## 📋 Overview

This repository contains professionally designed email templates for M Village's hotel operations, covering the complete customer journey from booking confirmation to post-stay surveys. All templates are built with responsive design principles and cross-client compatibility in mind.

## 🏗️ Repository Structure

### 📧 Email Templates by Category

#### 1. Booking Confirmations
- **`1.bk-loyalty/`** - Loyalty member booking confirmations
  - `bk-conf-EN.html` - English version
  - `bk-conf-VI.html` - Vietnamese version
- **`2.bk-non-loyalty/`** - Non-loyalty member booking confirmations
  - `bk-conf-non-loyalty-EN.html` - English version
  - `bk-conf-non-loyalty-VI.html` - Vietnamese version
- **`3.bk-b2b/`** - B2B booking confirmations
  - `bk-conf-b2b-EN.html` - English version
  - `bk-conf-b2b-VI.html` - Vietnamese version

#### 2. Customer Onboarding & Communication
- **`9.welcome/`** - Welcome emails for new members
  - `email_welcome_en.html` - English version
  - `email_welcome_vi.html` - Vietnamese version
- **`8.verify/`** - Email verification templates
  - `verify.html`
- **`10.remind-verify/`** - Email verification reminders
  - `remind-verify-EN.html` - English version
  - `remind-verify-VI.html` - Vietnamese version

#### 3. B2B Services
- **`4.b2b lead/`** - B2B lead generation templates
  - `b2b.html`
- **`19.b2b-reminder/`** - B2B follow-up reminders
  - `b2b-reminder-v2-en.html` - English version
  - `b2b-reminder-v2-vi.html` - Vietnamese version
  - `b2b-bao-gia.html` - Pricing information template
- **`21.b2b-send-pass/`** - B2B account credentials
  - `b2b-send-pass-en.html` - English version
  - `b2b-send-pass-vi.html` - Vietnamese version

#### 4. Financial & Invoicing
- **`5.einvoice/`** - Electronic invoice templates
  - `einvoice-email.html` - Email invoice template
  - `einvoice-pms-template.html` - PMS integration template
  - `einvoice-pms-updated.html` - Updated PMS template
  - `invoice-v2.html` - Version 2 invoice template

#### 5. Customer Feedback & Surveys
- **`6.survey-loyalty/`** - Post-stay surveys for loyalty members
  - `survey-loyalty-EN.html` - English version
  - `survey-loyalty-VI.html` - Vietnamese version
- **`7.survey-non-loyalty/`** - Post-stay surveys for non-loyalty members
  - `survey-non-loyalty-EN.html` - English version
  - `survey-non-loyalty-VI.html` - Vietnamese version

#### 6. Loyalty Program Management
- **`17.start-review-loyalty/`** - Loyalty review initiation
  - `start-review-loyalty-EN.html` - English version
  - `start-review-loyalty-VI.html` - Vietnamese version
- **`18.end-review-loyalty/`** - Loyalty review completion
  - `end-review-loyalty-EN.html` - English version
  - `end-review-loyalty-VI.html` - Vietnamese version
- **`13.upgrade-tier/`** - Loyalty tier upgrade notifications
  - `upgrade_tier_en.html` - English version
  - `upgrade_tier_vi.html` - Vietnamese version
- **`14.downgrade-tier/`** - Loyalty tier downgrade notifications
  - `downgrade_tier_en.html` - English version
  - `downgrade_tier_vi.html` - Vietnamese version

#### 7. Operational Communications
- **`20.aware-issue/`** - Issue awareness notifications
  - `aware-EN.html` - English version
  - `aware-VI.html` - Vietnamese version
- **`22.pre-arrival/`** - Pre-arrival communication
  - `pre-arrival_en.html` - English version
  - `pre-arrival_vi.html` - Vietnamese version

#### 8. Specialized Tools & Templates
- **`12.tool/`** - Utility tools and specialized templates
  - `account_deletion_tool.html` - Account deletion interface
  - `landlord-landing-page.html` - Landlord portal landing page
  - `original.html` - Original template reference
  - `survey-typeform-v1.html` - Typeform survey integration
- **`23.landlord/`** - Landlord-specific templates
  - `landlord.html` - Main landlord template
  - `landlord-demo.html` - Demo version

### 🔧 Development Tools
- **`15.python/`** - Python automation scripts
  - `send-b2b-lead.py` - Automated B2B lead email sender

### 📊 Documentation & Process
- **`16.flowchart-mermaidchart/`** - Process flowcharts
  - `MV-pickup-profile.mmd` - Profile pickup process flowchart
  - `MV-product-process.mmd` - Product process flowchart

## 🎨 Design Features

### Typography
- **Primary Font**: Be Vietnam Pro (Google Fonts)
- **Fallback Fonts**: Arial, Helvetica, sans-serif
- **Responsive Font Sizing**: Optimized for different email clients

### Color Scheme
- **Primary Background**: #f5f7fa
- **Content Background**: #ffffff
- **Text Color**: #333333
- **Accent Colors**: Brand-specific colors for M Village

### Responsive Design
- Mobile-first approach
- Cross-client compatibility (Outlook, Gmail, Apple Mail, etc.)
- MSO (Microsoft Outlook) specific optimizations
- Flexible table-based layouts

## 🚀 Usage

### Template Variables
Most templates use placeholder variables that should be replaced with actual data:
- `{{email}}` - Customer email address
- `{{password}}` - Account password (for B2B templates)
- `{{name}}` - Customer name
- `{{booking_id}}` - Booking reference number
- `{{check_in_date}}` - Check-in date
- `{{check_out_date}}` - Check-out date

### Python Integration
The `send-b2b-lead.py` script demonstrates how to integrate with M Village's API:
```python
API_URL = "https://api-user.mvillage.vn/api/me/notification/send-b2b-email"
```

### Email Client Testing
Templates are tested across major email clients:
- Microsoft Outlook (all versions)
- Gmail (web and mobile)
- Apple Mail
- Yahoo Mail
- Thunderbird

## 📱 Mobile Optimization

All templates include:
- Viewport meta tags for proper mobile rendering
- Responsive table structures
- Touch-friendly button sizes
- Optimized font sizes for mobile devices

## 🔧 Technical Specifications

### HTML Standards
- HTML5 DOCTYPE
- UTF-8 encoding
- Semantic HTML structure
- Accessibility attributes (ARIA roles)

### CSS Features
- Inline styles for maximum compatibility
- Media queries for responsive design
- Vendor prefixes for cross-browser support
- Conditional comments for Outlook

### Image Optimization
- WebP support with fallbacks
- Responsive image sizing
- Alt text for accessibility
- Lazy loading considerations

## 📝 Maintenance

### Version Control
- Each template category is organized in numbered folders
- Language variants clearly marked with EN/VI suffixes
- Version numbers included in filenames where applicable

### Updates
- Templates are regularly updated for new features
- Cross-client testing performed before deployment
- A/B testing results incorporated into design improvements

## 🤝 Contributing

When updating templates:
1. Test across multiple email clients
2. Maintain consistent branding and typography
3. Update both English and Vietnamese versions
4. Follow the existing folder structure
5. Include proper variable placeholders

## 📞 Support

For questions about template usage or customization, please contact the M Village development team.

---

*Last updated: December 2024*
