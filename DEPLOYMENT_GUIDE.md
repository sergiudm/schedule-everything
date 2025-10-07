# Documentation Deployment Guide

This guide explains how to deploy the Schedule Management documentation to GitHub Pages.

## Prerequisites

1. **Repository Settings**: Ensure you have admin access to the repository
2. **GitHub Pages**: GitHub Pages must be enabled in the repository settings

## GitHub Pages Configuration

### 1. Enable GitHub Pages in Repository Settings

1. Go to your repository on GitHub
2. Click on **Settings** tab
3. Scroll down to **Pages** section in the left sidebar
4. Under **Source**, select **GitHub Actions**
5. Click **Save**

### 2. Verify Workflow Permissions

The GitHub Actions workflow (`.github/workflows/deploy-docs.yml`) has been configured with the necessary permissions:

```yaml
permissions:
  contents: read
  pages: write
  id-token: write
```

### 3. Deployment Triggers

The documentation will be automatically deployed when:

- **Push to main branch**: Any changes to files in the `documentation/` directory or the workflow file itself
- **Manual trigger**: You can manually trigger deployment from the Actions tab

## Local Testing

Before deploying, you can test the documentation locally:

```bash
# Navigate to documentation directory
cd documentation

# Install dependencies
npm install

# Start development server
npm run start

# Build for production (to check for build errors)
npm run build
```

## Deployment Process

### Automatic Deployment

1. **Push changes** to the `main` branch that affect documentation files
2. **GitHub Actions** will automatically:
   - Build the documentation using Docusaurus
   - Deploy to GitHub Pages
   - Update the live site at `https://sergiudm.github.io/schedule_management/`

### Manual Deployment

1. Go to the **Actions** tab in your GitHub repository
2. Select **Deploy Documentation to GitHub Pages** workflow
3. Click **Run workflow**
4. Select the branch (usually `main`)
5. Click **Run workflow**

## Monitoring Deployment

### Check Deployment Status

1. Go to the **Actions** tab in your GitHub repository
2. Look for the latest **Deploy Documentation to GitHub Pages** workflow run
3. Click on the workflow run to see detailed logs

### Verify Deployment

After successful deployment:

1. Visit `https://sergiudm.github.io/schedule_management/`
2. Check that all pages load correctly
3. Verify that the multilingual support (English/Chinese) works
4. Test navigation and links

## Troubleshooting

### Common Issues

1. **Build Failures**: Check the workflow logs for build errors
2. **Broken Links**: The build warnings about broken anchors should be addressed
3. **Deployment Failures**: Ensure GitHub Pages is enabled in repository settings

### Build Warnings

The current build shows some broken anchor warnings. These should be fixed by updating the documentation files to use correct anchor links.

## Configuration Details

### Docusaurus Configuration

The documentation is configured with:
- **Base URL**: `/schedule_management/`
- **Organization**: `sergiudm`
- **Repository**: `schedule_management`
- **Multi-language support**: English and Chinese

### GitHub Actions Workflow

The workflow includes:
- **Build job**: Installs dependencies and builds the documentation
- **Deploy job**: Deploys to GitHub Pages (only on main branch pushes)
- **Caching**: Uses npm caching for faster builds
- **Concurrency**: Prevents concurrent deployments

## Next Steps

1. ✅ GitHub Actions workflow created
2. 🔄 Configure GitHub Pages in repository settings
3. 🔄 Push changes to trigger deployment
4. 🔄 Verify deployment success
5. 🔄 Address any build warnings or broken links

## Support

For issues with documentation deployment:
1. Check the GitHub Actions logs
2. Verify repository settings
3. Test locally before deployment
4. Review Docusaurus configuration in `documentation/docusaurus.config.ts`